#!/usr/bin/env node
import { FastMCP } from 'fastmcp';
import { z } from 'zod';
import {
  createWildcardCorsOptions,
  startFastMcpHttpProxy
} from '@ai-universe/mcp-server-utils';
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdtemp, readFile, readdir, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);
const packageRoot = resolve(__dirname, '..');
const pythonAssetsDir = join(packageRoot, 'python');
const repositoryRoot = resolve(packageRoot, '..');
const bundledCrawlerScript = join(pythonAssetsDir, 'crawler.py');
const fallbackCrawlerScript = join(repositoryRoot, 'crawler.py');
const hasBundledCrawler = existsSync(bundledCrawlerScript);
const crawlerScript = hasBundledCrawler ? bundledCrawlerScript : fallbackCrawlerScript;
const crawlerWorkingDirectory = hasBundledCrawler ? pythonAssetsDir : repositoryRoot;

const DEFAULT_MAX_DEPTH = 1;
const DEFAULT_DELAY = 1;

async function runCrawler({ url, maxDepth = DEFAULT_MAX_DEPTH, delay = DEFAULT_DELAY }) {
  const tempDir = await mkdtemp(join(tmpdir(), 'crawler-'));
  const outputDir = join(tempDir, 'output');
  const pythonBin = process.env.CRAWLER_PYTHON_BIN || 'python3';

  const args = [
    crawlerScript,
    url,
    '--max-depth',
    String(maxDepth),
    '--delay',
    String(delay),
    '--output-dir',
    outputDir
  ];

  const stdoutChunks = [];
  const stderrChunks = [];

  try {
    await new Promise((resolvePromise, rejectPromise) => {
      const child = spawn(pythonBin, args, {
        cwd: crawlerWorkingDirectory,
        stdio: ['ignore', 'pipe', 'pipe']
      });

      child.stdout?.on('data', (chunk) => {
        stdoutChunks.push(chunk.toString());
      });

      child.stderr?.on('data', (chunk) => {
        stderrChunks.push(chunk.toString());
      });

      child.on('error', (error) => {
        rejectPromise(error);
      });

      child.on('close', (code) => {
        if (code === 0) {
          resolvePromise();
        } else {
          const stderrOutput = stderrChunks.join('').trim();
          const stdoutOutput = stdoutChunks.join('').trim();
          const message = `Crawler exited with code ${code}`;
          const details = stderrOutput || stdoutOutput;
          const error = new Error(details ? `${message}: ${details}` : message);
          rejectPromise(error);
        }
      });
    });

    const combinedPath = join(outputDir, 'combined_crawl.md');
    const combinedMarkdown = await readFile(combinedPath, 'utf8');

    const documents = [];
    for (const entry of await readdir(outputDir)) {
      if (!entry.endsWith('.md') || entry === 'combined_crawl.md') {
        continue;
      }

      const docPath = join(outputDir, entry);
      const content = await readFile(docPath, 'utf8');
      documents.push({
        name: entry,
        content
      });
    }

    return {
      combinedMarkdown,
      documents,
      stdout: stdoutChunks.join(''),
      stderr: stderrChunks.join('')
    };
  } finally {
    await rm(tempDir, { recursive: true, force: true }).catch((error) => {
      console.warn(`Failed to cleanup temp directory ${tempDir}:`, error.message);
    });
  }
}

export function createCrawlerServer() {
  const server = new FastMCP({
    name: 'ai-web-crawler',
    version: '0.1.0',
    instructions: 'Provide Google Docs URLs to receive crawled Markdown content.'
  });

  server.addTool({
    name: 'crawl_google_doc',
    description: 'Crawl a Google Docs URL and return the discovered Markdown content.',
    parameters: z.object({
      url: z.string().url('A valid Google Docs URL is required.'),
      maxDepth: z
        .number()
        .int()
        .min(0)
        .max(5)
        .default(DEFAULT_MAX_DEPTH)
        .describe('Maximum link depth to crawl (0 fetches only the initial URL).'),
      delay: z
        .number()
        .min(0)
        .max(10)
        .default(DEFAULT_DELAY)
        .describe('Delay in seconds between requests to avoid rate limiting.')
    }),
    execute: async (args) => {
      const { combinedMarkdown, documents, stdout, stderr } = await runCrawler(args);

      const documentSummary = documents
        .map((doc) => `- ${doc.name}`)
        .join('\n');

      const summaryText = [
        `Crawled URL: ${args.url}`,
        `Max depth: ${args.maxDepth ?? DEFAULT_MAX_DEPTH}`,
        documents.length ? 'Discovered documents:\n' + documentSummary : 'No linked documents were saved.',
        stdout.trim() ? `\nCrawler output:\n${stdout.trim()}` : '',
        stderr.trim() ? `\nCrawler warnings:\n${stderr.trim()}` : ''
      ]
        .filter(Boolean)
        .join('\n\n');

      return {
        content: [
          {
            type: 'text',
            text: combinedMarkdown,
            mimeType: 'text/markdown'
          },
          {
            type: 'text',
            text: summaryText
          }
        ]
      };
    }
  });

  return server;
}

export async function startCrawlerServer(options = {}) {
  const {
    host = process.env.MCP_HOST || '0.0.0.0',
    port: optionPort,
    allowedOrigins: optionAllowedOrigins,
    proxyPath = process.env.MCP_PROXY_PATH || '/mcp',
    healthPath = process.env.MCP_HEALTH_PATH || '/healthz',
    logger = console
  } = options;

  const port = (() => {
    if (optionPort !== undefined) {
      const numericPort = Number(optionPort);
      if (!Number.isInteger(numericPort) || numericPort <= 0 || numericPort > 65535) {
        throw new Error(`Invalid port number: ${optionPort}`);
      }
      return numericPort;
    }

    const envPort = process.env.PORT || process.env.HTTP_PORT;
    if (envPort !== undefined) {
      const numericPort = Number(envPort);
      if (!Number.isInteger(numericPort) || numericPort <= 0 || numericPort > 65535) {
        throw new Error(`Invalid port number: ${envPort}`);
      }
      return numericPort;
    }

    return 8000;
  })();

  const allowedOrigins = (() => {
    if (optionAllowedOrigins !== undefined) {
      const normalized = (Array.isArray(optionAllowedOrigins)
        ? optionAllowedOrigins
        : [optionAllowedOrigins]
      )
        .map((value) => String(value).trim())
        .filter(Boolean);

      if (!normalized.length) {
        throw new Error('allowedOrigins must include at least one origin.');
      }

      return normalized;
    }

    if (process.env.MCP_ALLOWED_ORIGINS) {
      const normalized = process.env.MCP_ALLOWED_ORIGINS.split(',')
        .map((value) => value.trim())
        .filter(Boolean);

      if (!normalized.length) {
        throw new Error('MCP_ALLOWED_ORIGINS must contain at least one origin.');
      }

      return normalized;
    }

    return ['*'];
  })();

  const server = createCrawlerServer();

  const corsOptions = createWildcardCorsOptions({
    allowedOrigins,
    allowNullOrigin: true
  });

  const result = await startFastMcpHttpProxy({
    server,
    listenPort: port,
    host,
    corsOptions,
    proxyPath,
    logger,
    configureApp: (app) => {
      app.get(healthPath, (_req, res) => {
        res.json({ status: 'ok' });
      });
    }
  });

  logger.info?.(
    `AI Web Crawler MCP server listening on http://${host}:${port}${proxyPath} (internal MCP port ${result.mcpPort})`
  );
  logger.info?.(`Health check available at http://${host}:${port}${healthPath}`);

  return { server, ...result };
}

const isCliEntry = process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1];

if (isCliEntry) {
  startCrawlerServer().catch((error) => {
    console.error('Failed to start AI Web Crawler MCP server');
    console.error(error);
    process.exit(1);
  });
}
