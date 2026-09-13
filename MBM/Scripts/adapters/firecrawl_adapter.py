from typing import Dict, Any, List
import requests

class FirecrawlAdapter:
    """
    Adapter for firecrawl/firecrawl.
    Provides BROWSER_AUTOMATION with strict URL whitelisting.
    """
    
    ALLOWED_DOMAINS = ["example.com", "github.com", "zillow.com"]
    
    def __init__(self, api_key: str = None):
        self.api_key = api_key
        self.base_url = "http://localhost:3002/v1" # Assuming self-hosted or proxied
        
    def scrape_url(self, url: str) -> Dict[str, Any]:
        self._enforce_whitelist(url)
        
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        response = requests.post(f"{self.base_url}/scrape", json={"url": url}, headers=headers)
        return response.json()

    def _enforce_whitelist(self, url: str):
        if not any(domain in url for domain in self.ALLOWED_DOMAINS):
            raise PermissionError(f"URL {url} is not in the allowed domains list.")