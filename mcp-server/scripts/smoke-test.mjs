#!/usr/bin/env node
import { startCrawlerServer } from '../src/index.js';

async function main() {
  const port = 8123;
  const healthPath = '/healthz-smoke';
  const { expressServer, server } = await startCrawlerServer({
    port,
    logger: console,
    healthPath
  });

  try {
    const response = await fetch(`http://127.0.0.1:${port}${healthPath}`);
    if (!response.ok) {
      throw new Error(`Health check failed with status ${response.status}`);
    }
    const body = await response.json();
    if (body?.status !== 'ok') {
      throw new Error(`Unexpected health response: ${JSON.stringify(body)}`);
    }
    console.log('Health check passed:', body);
  } finally {
    await Promise.all([
      new Promise((resolve) => {
        expressServer.close((error) => {
          if (error && error.code !== 'ERR_SERVER_NOT_RUNNING') {
            console.warn('Express server close warning:', error);
          }
          resolve();
        });
      }),
      (async () => {
        if (typeof server?.close === 'function') {
          try {
            await server.close();
          } catch (error) {
            console.warn('FastMCP close warning:', error);
          }
        }
      })()
    ]);
  }
}

main().catch((error) => {
  console.error('MCP smoke test failed');
  console.error(error);
  process.exit(1);
}).then(() => {
  process.exit(0);
});
