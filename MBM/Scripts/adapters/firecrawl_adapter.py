"""Firecrawl Adapter for JARVIS Ecosystem.

Provides BROWSER_AUTOMATION with strict URL whitelisting and fail-closed policy enforcement.
"""
from typing import Dict, Any, Optional
from urllib.parse import urlparse
import requests


class FirecrawlAdapter:
    """
    Adapter for firecrawl/firecrawl.
    Provides BROWSER_AUTOMATION with strict URL whitelisting.
    """

    ALLOWED_DOMAINS = ["example.com", "github.com", "zillow.com"]

    def __init__(self, api_key: Optional[str] = None, base_url: Optional[str] = None, timeout: float = 30.0):
        self.api_key = api_key
        self.base_url = base_url or "http://localhost:3002/v1"
        self.timeout = timeout

    def scrape_url(self, url: str, approval: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.api_key:
            raise PermissionError("Firecrawl API key is required. Uncredentialed access is denied.")
        host = self._enforce_whitelist(url)
        self._verify_mcp_approval(host, approval=approval)

        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            response = requests.post(
                f"{self.base_url}/scrape",
                json={"url": url},
                headers=headers,
                timeout=self.timeout
            )
        except requests.exceptions.Timeout as exc:
            raise RuntimeError(f"Firecrawl scrape timed out after {self.timeout}s: {exc}") from exc
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"Firecrawl connection error: {exc}") from exc

        if not response.ok:
            raise RuntimeError(f"Firecrawl scrape failed with HTTP {response.status_code}")
        return response.json()


    def _enforce_whitelist(self, url: str) -> str:
        if not isinstance(url, str) or not url:
            raise ValueError("url must be a non-empty string")
        if any(c in url for c in (" ", "\t", "\n", "\r", "\x00")):
            raise ValueError("url contains whitespace or control characters")
        try:
            parsed = urlparse(url)
        except Exception as exc:
            raise ValueError(f"malformed url: {exc}") from exc
        if parsed.scheme.lower() not in ("http", "https"):
            raise ValueError("only http/https urls are allowed")
        host = (parsed.hostname or "").lower()
        if not host:
            raise ValueError("url has no hostname")
        if not any(host == d or host.endswith("." + d) for d in self.ALLOWED_DOMAINS):
            raise PermissionError(f"URL host '{host}' is not in the allowed domains list.")
        return host

    def _verify_mcp_approval(self, host: str, approval: Optional[Dict[str, Any]] = None) -> None:
        from jarvis_control_plane.policy import ActionClass, PolicyVerdict, evaluate

        decision = evaluate(
            f"scrape firecrawl url at {host}",
            approval=approval,
            action_class=ActionClass.EXTERNAL_SIDE_EFFECT,
        )
        if decision.verdict != PolicyVerdict.ALLOW:
            raise PermissionError(f"Policy denied Firecrawl scrape: {decision.reason}")
