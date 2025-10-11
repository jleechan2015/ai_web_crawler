"""
Google Docs scraper that converts documents to markdown.
"""
import requests
import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from markdownify import markdownify
import time
import logging


class GoogleDocsScraper:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        self.visited_urls = set()
        
    def convert_google_docs_url(self, url):
        """Convert various Google Docs URL formats to export format."""
        # Extract document ID from various formats
        doc_id_pattern = r'/document/d/([a-zA-Z0-9-_]+)'
        match = re.search(doc_id_pattern, url)
        
        if match:
            doc_id = match.group(1)
            # Convert to export URL for HTML
            return f"https://docs.google.com/document/d/{doc_id}/export?format=html"
        
        return url
    
    def scrape_google_doc(self, url):
        """Scrape a Google Doc and return content and links."""
        if url in self.visited_urls:
            logging.info(f"Already visited: {url}")
            return None, []
            
        self.visited_urls.add(url)
        
        try:
            export_url = self.convert_google_docs_url(url)
            logging.info(f"Fetching: {export_url}")
            
            response = self.session.get(export_url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            
            # Extract the main content
            content = soup.get_text()
            
            # Convert to markdown using markdownify
            markdown_content = markdownify(str(soup), heading_style="ATX")
            
            # Extract links that might be Google Docs
            links = self.extract_google_docs_links(soup)
            
            return markdown_content, links
            
        except Exception as e:
            logging.error(f"Error scraping {url}: {str(e)}")
            return None, []
    
    def extract_google_docs_links(self, soup):
        """Extract Google Docs links from the content."""
        links = []
        
        # Find all links
        for link in soup.find_all('a', href=True):
            href = link['href']
            
            # Check if it's a Google Docs link
            if 'docs.google.com/document' in href:
                # Clean up the URL
                if href.startswith('https://www.google.com/url?q='):
                    # Extract the actual URL from Google's redirect
                    match = re.search(r'q=([^&]+)', href)
                    if match:
                        import urllib.parse
                        href = urllib.parse.unquote(match.group(1))
                
                if href not in self.visited_urls:
                    links.append(href)
        
        return links
    
    def crawl_recursive(self, start_url, max_depth=3, delay=1):
        """Recursively crawl Google Docs starting from a URL."""
        crawl_queue = [(start_url, 0)]  # (url, depth)
        all_content = {}
        
        while crawl_queue:
            current_url, depth = crawl_queue.pop(0)
            
            if depth > max_depth:
                continue
                
            logging.info(f"Crawling (depth {depth}): {current_url}")
            
            content, links = self.scrape_google_doc(current_url)
            
            if content:
                # Generate a filename from the URL
                filename = self.generate_filename(current_url)
                all_content[filename] = {
                    'content': content,
                    'url': current_url,
                    'depth': depth
                }
                
                # Add discovered links to queue
                for link in links:
                    if link not in self.visited_urls:
                        crawl_queue.append((link, depth + 1))
            
            # Be respectful with delays
            if delay > 0:
                time.sleep(delay)
        
        return all_content
    
    def generate_filename(self, url):
        """Generate a safe filename from URL."""
        # Extract document ID or create from URL
        doc_id_pattern = r'/document/d/([a-zA-Z0-9-_]+)'
        match = re.search(doc_id_pattern, url)
        
        if match:
            return f"doc_{match.group(1)}.md"
        else:
            # Fallback: create filename from URL
            safe_url = re.sub(r'[^\w\-_\.]', '_', url.split('/')[-1])
            return f"doc_{safe_url}.md"
    
    def save_content(self, all_content, output_dir="output"):
        """Save all crawled content to files."""
        import os
        
        os.makedirs(output_dir, exist_ok=True)
        
        # Save individual files
        for filename, data in all_content.items():
            filepath = os.path.join(output_dir, filename)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(f"# Document from: {data['url']}\n")
                f.write(f"# Crawl depth: {data['depth']}\n\n")
                f.write(data['content'])
            
            logging.info(f"Saved: {filepath}")
        
        # Create a combined file
        combined_path = os.path.join(output_dir, "combined_crawl.md")
        with open(combined_path, 'w', encoding='utf-8') as f:
            f.write("# Combined Web Crawl Results\n\n")
            
            for filename, data in sorted(all_content.items(), key=lambda x: x[1]['depth']):
                f.write(f"## {filename}\n")
                f.write(f"Source: {data['url']} (depth: {data['depth']})\n\n")
                f.write(data['content'])
                f.write("\n\n---\n\n")
        
        logging.info(f"Combined file saved: {combined_path}")
        return len(all_content)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    scraper = GoogleDocsScraper()
    test_url = "https://docs.google.com/document/d/1rsaK53T3Lg5KoGwvf8ukOUvbELRtH-V0LnOIFDxBryE/mobilebasic"
    
    results = scraper.crawl_recursive(test_url, max_depth=2)
    count = scraper.save_content(results)
    
    print(f"Crawled and saved {count} documents")
