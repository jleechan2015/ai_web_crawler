# AI Web Crawler

A intelligent web crawler that reads Google Docs and follows sub-links to download entire document trees as markdown files.

## Features

- Scrapes Google Docs content and converts to markdown
- Discovers and follows links within documents
- Recursive crawling of linked documents
- Intelligent content extraction and formatting
- Outputs clean markdown files

## Usage

```bash
python crawler.py <google_docs_url>
```

## Requirements

- Python 3.8+
- requests
- beautifulsoup4
- markdownify
- urllib3

## Installation

```bash
pip install -r requirements.txt
```