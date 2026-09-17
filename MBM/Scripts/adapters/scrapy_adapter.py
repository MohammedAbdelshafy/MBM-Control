"""Scrapy Adapter for JARVIS Ecosystem.

Exposes CRAWLING with domain allowlist enforcement and fail-closed policy gates.
"""
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse


class ScrapyAdapter:
    """
    Adapter for scrapy/scrapy.
    Exposes CRAWLING with Dry-run modes, enforcing no writes outside the sandbox.
    """
    def __init__(self, allowed_domains: Optional[List[str]] = None):
        self.allowed_domains = [d.lower() for d in (allowed_domains or [])]

    def run_spider(self, start_url: str, dry_run: bool = True, approval: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._enforce_domain(start_url)
        self._verify_mcp_approval(start_url=start_url, approval=approval)
        raise NotImplementedError(
            "Scrapy transport is not implemented without active spider runner. "
            "Direct execution from this stub is not supported without fabricated success."
        )

    def _enforce_domain(self, url: str) -> str:
        if not isinstance(url, str) or not url:
            raise ValueError("URL must be a non-empty string.")
        try:
            parsed = urlparse(url)
        except Exception as exc:
            raise ValueError(f"Malformed URL: {exc}") from exc
        host = (parsed.hostname or "").lower()
        if not host or not any(host == d or host.endswith("." + d) for d in self.allowed_domains):
            raise PermissionError(f"URL '{url}' host '{host}' is not in allowed domains list.")
        return host

    def _verify_mcp_approval(self, start_url: str, approval: Optional[Dict[str, Any]] = None) -> None:
        from jarvis_control_plane.policy import ActionClass, PolicyVerdict, evaluate

        decision = evaluate(
            f"run scrapy spider on {start_url}",
            approval=approval,
            action_class=ActionClass.EXTERNAL_SIDE_EFFECT,
        )
        if decision.verdict != PolicyVerdict.ALLOW:
            raise PermissionError(f"Policy denied Scrapy execution: {decision.reason}")
