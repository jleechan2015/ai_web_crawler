# AI Web Crawler

A intelligent web crawler that reads Google Docs and follows sub-links to download entire document trees as markdown files.

## Features

- Scrapes Google Docs content and converts to markdown
- Discovers and follows links within documents
- Recursive crawling of linked documents
- Intelligent content extraction and formatting
- Outputs clean markdown files

## Usage

Basic usage:
```bash
python crawler.py <google_docs_url>
```

Advanced usage with options:
```bash
python crawler.py "https://docs.google.com/document/d/your-doc-id/mobilebasic" \
  --max-depth 3 \
  --delay 1.0 \
  --output-dir output \
  --verbose
```

## Example

```bash
python crawler.py "https://docs.google.com/document/d/1rsaK53T3Lg5KoGwvf8ukOUvbELRtH-V0LnOIFDxBryE/mobilebasic"
```

This will:
- Start from the specified Google Doc
- Follow all Google Docs links found within
- Recursively crawl up to depth 3 (configurable)
- Save individual markdown files to `output/`
- Create a combined `output/combined_crawl.md` file

## Command Line Options

- `--max-depth N`: Maximum crawl depth (default: 3)
- `--delay N`: Delay between requests in seconds (default: 1.0)
- `--output-dir DIR`: Output directory for markdown files (default: output)
- `--verbose, -v`: Enable verbose logging

## Requirements

- Python 3.8+
- requests
- beautifulsoup4
- markdownify
- urllib3
- lxml

## Installation

```bash
pip install -r requirements.txt
```

## Output

The crawler generates:
- Individual markdown files for each discovered document
- A combined `combined_crawl.md` file with all content
- Preserves document structure and formatting
- Includes source URLs and crawl depth information

## Test Results

Successfully tested on a complex Google Docs tree, crawling 39 documents and generating 5,691 lines of combined markdown content.

## Continuous deployment from restricted networks

To support enterprise environments protected by VPC Service Controls, this repository ships with a GitHub Actions workflow and a reusable Python package that orchestrate asynchronous deploy builds. The workflow triggers a remote builder, polls for completion, updates the pull request with rich status cards and preview links, and now finishes with MCP smoke tests to ensure the packaged server continues to boot cleanly. See [`docs/ci-preview.md`](docs/ci-preview.md) for setup instructions and customization tips.
