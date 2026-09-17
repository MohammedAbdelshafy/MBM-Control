"""Hardened Playwright BROWSER_AUTOMATION adapter (Slice 1).

Read-only page-text extraction constrained to an explicit domain allowlist.
No network, browser, or subprocess at import time — the real Playwright
driver is imported lazily only when no injectable ``fetcher`` is supplied,
so unit tests stay hermetic.

Security properties:
- Exact/suffix hostname match via ``urllib.parse`` (no substring check).
- Only http/https with a hostname; control chars / overlong URLs rejected.
- ``policy.evaluate(..., action_class=READ)`` defense-in-depth; DENY raises.
- Content truncated to ``max_content_chars``; timeouts surfaced with
  ``error_kind="timeout"`` so the MCP bus retry policy applies.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional
from urllib.parse import urlparse

MAX_URL_LENGTH = 2048
DEFAULT_TIMEOUT_SEC = 30
DEFAULT_MAX_CONTENT_CHARS = 20000


class PlaywrightAdapter:
    """
    Adapter for microsoft/playwright.
    Exposes BROWSER_AUTOMATION restricting to approved domains.
    """

    ALLOWED_DOMAINS: List[str] = ["example.com", "github.com", "zillow.com"]

    def __init__(
        self,
        fetcher: Optional[Callable[[str], str]] = None,
        allowed_domains: Optional[List[str]] = None,
        timeout_sec: int = DEFAULT_TIMEOUT_SEC,
        max_content_chars: int = DEFAULT_MAX_CONTENT_CHARS,
    ) -> None:
        self._fetcher = fetcher
        self.allowed_domains = [
            d.lower() for d in (allowed_domains or list(self.ALLOWED_DOMAINS))
        ]
        self.timeout_sec = timeout_sec
        self.max_content_chars = max_content_chars

    # -- gating ---------------------------------------------------------
    def _parse_and_enforce(self, url: Any) -> str:
        if not isinstance(url, str) or not url:
            raise ValueError("url must be a non-empty string")
        if len(url) > MAX_URL_LENGTH:
            raise ValueError(f"url exceeds {MAX_URL_LENGTH} chars")
        if any(c in url for c in (" ", "\t", "\n", "\r", "\x00")):
            raise ValueError("url contains whitespace/control characters")
        try:
            parsed = urlparse(url)
        except Exception as exc:
            raise ValueError(f"malformed url: {exc}") from exc
        if parsed.scheme.lower() not in ("http", "https"):
            raise ValueError("only http/https urls are allowed")
        host = (parsed.hostname or "").lower()
        if not host:
            raise ValueError("url has no hostname")
        if not any(host == d or host.endswith("." + d) for d in self.allowed_domains):
            raise PermissionError(
                f"URL host '{host}' is not in the allowed domains list."
            )
        return host

    def _verify_mcp_approval(self, host: str, approval: Optional[Dict[str, Any]] = None) -> None:
        from jarvis_control_plane.policy import (
            ActionClass,
            PolicyVerdict,
            evaluate,
        )

        decision = evaluate(
            f"read browser page at {host}",
            approval=approval,
            action_class=ActionClass.READ,
        )
        if decision.verdict is PolicyVerdict.DENY:
            raise PermissionError(f"policy denied browser read: {decision.reason}")

    # -- fetching -------------------------------------------------------
    def _playwright_fetch(self, url: str) -> str:
        try:
            from playwright.sync_api import sync_playwright
        except Exception as exc:
            raise RuntimeError(
                "playwright is not installed; pass a fetcher= callable or "
                "`pip install playwright` + `playwright install chromium`"
            ) from exc
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, timeout=self.timeout_sec * 1000)
                try:
                    return page.inner_text("body")
                except Exception:
                    return page.content()
            finally:
                browser.close()

    def extract(
        self, url: str, approval: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Fetch page text. Raises ValueError/PermissionError on bad input."""
        host = self._parse_and_enforce(url)
        self._verify_mcp_approval(host, approval)
        fetch = self._fetcher or self._playwright_fetch
        try:
            content = fetch(url)
        except PermissionError:
            raise
        except ValueError:
            raise
        except TimeoutError as exc:
            wrapped = RuntimeError(str(exc)[:500])
            setattr(wrapped, "error_kind", "timeout")
            raise wrapped from exc
        except Exception as exc:
            msg = str(exc).lower()
            kind = "timeout" if "timeout" in msg or "timed out" in msg else "provider_unavailable"
            wrapped = RuntimeError(str(exc)[:500])
            setattr(wrapped, "error_kind", kind)
            raise wrapped from exc
        if not isinstance(content, str):
            content = str(content)
        truncated = len(content) > self.max_content_chars
        return {
            "status": "success",
            "url": url,
            "host": host,
            "content": content[: self.max_content_chars],
            "content_length": len(content),
            "truncated": truncated,
        }

    async def navigate_and_extract(
        self, url: str, approval: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Async-compat wrapper (runs the sync fetcher; no event-loop I/O)."""
        return self.extract(url, approval=approval)
