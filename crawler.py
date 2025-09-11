#!/usr/bin/env python3
"""
Main crawler CLI interface.
"""
import argparse
import logging
import sys
from google_docs_scraper import GoogleDocsScraper


def main():
    parser = argparse.ArgumentParser(description='AI Web Crawler for Google Docs')
    parser.add_argument('url', help='Starting Google Docs URL to crawl')
    parser.add_argument('--max-depth', type=int, default=3, help='Maximum crawl depth (default: 3)')
    parser.add_argument('--delay', type=float, default=1.0, help='Delay between requests in seconds (default: 1.0)')
    parser.add_argument('--output-dir', default='output', help='Output directory for markdown files (default: output)')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose logging')
    
    args = parser.parse_args()
    
    # Set up logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    # Validate URL
    if 'docs.google.com/document' not in args.url:
        print("Error: URL must be a Google Docs document", file=sys.stderr)
        sys.exit(1)
    
    try:
        scraper = GoogleDocsScraper()
        
        print(f"Starting crawl from: {args.url}")
        print(f"Max depth: {args.max_depth}")
        print(f"Output directory: {args.output_dir}")
        print()
        
        # Start crawling
        results = scraper.crawl_recursive(
            args.url, 
            max_depth=args.max_depth,
            delay=args.delay
        )
        
        if not results:
            print("No content was crawled. Check the URL and try again.", file=sys.stderr)
            sys.exit(1)
        
        # Save results
        count = scraper.save_content(results, args.output_dir)
        
        print(f"\n✅ Successfully crawled and saved {count} documents")
        print(f"📁 Output saved to: {args.output_dir}/")
        print(f"📄 Combined file: {args.output_dir}/combined_crawl.md")
        
    except KeyboardInterrupt:
        print("\n❌ Crawl interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error during crawl: {str(e)}", file=sys.stderr)
        logging.exception("Full error details:")
        sys.exit(1)


if __name__ == "__main__":
    main()