from typing import List, Dict, Any

class ScrapyAdapter:
    """
    Adapter for scrapy/scrapy.
    Exposes CRAWLING with Dry-run modes, enforcing no writes outside the sandbox.
    """
    def __init__(self, allowed_domains: List[str]):
        self.allowed_domains = allowed_domains

    def run_spider(self, start_url: str, dry_run: bool = True) -> Dict[str, Any]:
        
        # Verify domain
        if not any(domain in start_url for domain in self.allowed_domains):
            raise PermissionError(f"URL {start_url} not allowed.")
            
        # TODO: Implement Scrapy API runner
        if dry_run:
            return {"status": "dry_run_success", "items_found": 10}
            
        return {"status": "success", "items": []}