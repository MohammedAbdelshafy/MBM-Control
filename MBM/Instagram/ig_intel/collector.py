"""Instagram Reel collector.

Reads Reels from the operator's authenticated Instagram session. It prefers the
chrome-devtools MCP (a Chrome already logged in, launched with
--remote-debugging-port=9222). If that transport is unavailable it falls back to
a Playwright-driven Chrome profile that reuses the operator's cookies.

IMPORTANT: This module only reads content the logged-in account can legitimately
view. It never submits credentials or attempts to bypass authentication.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from .config import Config
from .schema import reel_id_from_url


@dataclass
class CollectedReel:
    reel_id: str
    url: str
    creator: str = ""
    caption: str = ""
    date_saved: str = ""
    metrics: dict = None
    video_url: str = ""
    thumbnail_url: str = ""
    source: str = "saved"

    def __post_init__(self):
        if self.metrics is None:
            self.metrics = {}


class InstagramCollector:
    """Collects reel metadata via the authenticated browser session."""

    def __init__(self, config: Config, log: Callable[[str], None] = print):
        self.config = config
        self.log = log
        self._mcp = None
        self._playwright = None

    # --- transport selection -------------------------------------------
    def _ensure_transport(self):
        if self.config.browser_mode == "chrome-devtools-mcp":
            self._mcp = self._connect_devtools()
            if self._mcp:
                return "mcp"
        # fallback to playwright
        pw = self._connect_playwright()
        if pw:
            return "playwright"
        raise RuntimeError(
            "No browser transport available. Start Chrome with "
            "--remote-debugging-port=9222 (authenticated) or configure a "
            "playwright_profile with logged-in cookies."
        )

    def _connect_devtools(self):
        """Probe the chrome-devtools MCP endpoint. Returns a thin wrapper or None."""
        try:
            import urllib.request
            import urllib.error

            url = self.config.devtools_url.rstrip("/") + "/json/version"
            req = urllib.request.Request(url, headers={"User-Agent": "Antigravity-MCP/1.0"})
            with urllib.request.urlopen(req, timeout=2) as r:
                data = json.loads(r.read().decode())
            self.log(f"[devtools] connected: {data.get('Browser', 'Chrome')}")
            return _DevToolsMCP(self.config.devtools_url, self.log)
        except Exception as e:  # noqa: BLE001
            self.log(f"[devtools-mcp] Endpoint not reachable ({e}). Falling back to Playwright transport.")
            return None

    def _connect_playwright(self):
        if not self.config.playwright_profile:
            return None
        try:
            from playwright.sync_api import sync_playwright

            self._pw_ctx = sync_playwright().start()
            browser = self._pw_ctx.chromium.launch_persistent_context(
                self.config.playwright_profile,
                headless=self.config.headless,
            )
            self._playwright = browser
            self.log("[playwright] connected using persistent profile")
            return browser
        except Exception as e:  # noqa: BLE001
            self.log(f"[playwright] not available: {e}")
            return None

    # --- collection ----------------------------------------------------
    def collect(self) -> list[CollectedReel]:
        transport = self._ensure_transport()
        self.log(f"[collector] transport={transport}")
        reels: list[CollectedReel] = []
        seen = set()

        def _add(r: CollectedReel):
            if r.reel_id in seen or not r.url:
                return
            seen.add(r.reel_id)
            reels.append(r)

        if self.config.sources_saved:
            self._scroll_source("saved", _add)
        if self.config.sources_liked:
            self._scroll_source("liked", _add)
        if self.config.sources_collections:
            for name in self.config.collection_names or ["*"]:
                self._scroll_source(f"collection:{name}", _add)
        if self.config.sources_bookmarks:
            self._scroll_source("bookmarks", _add)
        if self.config.sources_following:
            self._scroll_source("following", _add)
        if self.config.sources_explore:
            self._scroll_source("explore", _add)
        for handle in self.config.creators:
            self._scroll_source(f"creator:{handle}", _add)

        return reels[: self.config.max_reels_per_run]

    def _scroll_source(self, source: str, add: Callable[[CollectedReel], None]):
        self.log(f"[collector] scanning source={source}")
        # The actual DOM scraping differs per transport. Delegate to transport.
        if self._mcp:
            items = self._mcp.scroll_reels(source)
        elif self._playwright:
            items = self._playwright_scrape(source)
        else:
            items = []
        for it in items:
            rid = reel_id_from_url(it.get("url", ""))
            add(CollectedReel(
                reel_id=rid,
                url=it.get("url", ""),
                creator=it.get("creator", ""),
                caption=it.get("caption", ""),
                date_saved=it.get("date_saved", ""),
                metrics=it.get("metrics", {}),
                video_url=it.get("video_url", ""),
                thumbnail_url=it.get("thumbnail_url", ""),
                source=source,
            ))
        time.sleep(self.config.rate_limit_seconds)

    def _playwright_scrape(self, source: str) -> list[dict]:
        """Collect reel grid URLs, then per-reel detail (caption/creator/video)."""
        browser = self._playwright
        page = browser.new_page()
        url = self._source_url(source)
        page.goto(url, wait_until="networkidle", timeout=30000)
        page.wait_for_timeout(2000)
        cards = page.query_selector_all("a[href*='/reel/'], a[href*='/p/']")
        urls: list[str] = []
        for c in cards:
            href = c.get_attribute("href") or ""
            if "/reel/" not in href and "/p/" not in href:
                continue
            full = f"https://www.instagram.com{href}" if href.startswith("/") else href
            if full not in urls:
                urls.append(full)
        page.close()

        out: list[dict] = []
        for u in urls:
            out.append(self._playwright_detail(browser, u))
            time.sleep(self.config.rate_limit_seconds)
        return out

    def _playwright_detail(self, browser, reel_url: str) -> dict:
        """Open a single reel and extract creator, caption, video src, thumbnail."""
        page = browser.new_page()
        try:
            page.goto(reel_url, wait_until="networkidle", timeout=30000)
            page.wait_for_timeout(1500)
            # creator handle from the profile link near the top of the reel
            creator = ""
            handle_el = page.query_selector("article a[href*='/']:not([href*='/reel/'])")
            if handle_el:
                h = handle_el.get_attribute("href") or ""
                creator = "@" + h.strip("/").split("/")[0].lstrip("@")
            # caption
            caption = ""
            cap_el = page.query_selector("article div[role='button'] span")
            if cap_el:
                caption = cap_el.inner_text() or ""
            # video source
            video_url = ""
            vid = page.query_selector("article video")
            if vid:
                video_url = vid.get_attribute("src") or ""
            # thumbnail (poster) as fallback media
            thumb = page.query_selector("article video[poster]")
            thumb_url = thumb.get_attribute("poster") if thumb else ""
            return {
                "url": reel_url,
                "creator": creator,
                "caption": caption,
                "video_url": video_url,
                "thumbnail_url": thumb_url,
            }
        except Exception as e:  # noqa: BLE001
            self.log(f"[playwright] detail failed for {reel_url}: {e}")
            return {"url": reel_url}
        finally:
            page.close()

    @staticmethod
    def _source_url(source: str) -> str:
        base = "https://www.instagram.com"
        if source == "saved":
            return f"{base}/saved/"
        if source == "liked":
            return f"{base}/p/"
        if source.startswith("collection:"):
            return f"{base}/saved/"
        if source == "following":
            return f"{base}/"
        if source == "explore":
            return f"{base}/explore/"
        if source == "bookmarks":
            return f"{base}/saved/"
        if source.startswith("creator:"):
            handle = source.split(":", 1)[1]
            return f"{base}/{handle.lstrip('@')}/"
        return f"{base}/saved/"


class _DevToolsMCP:
    """Thin wrapper over the chrome-devtools MCP HTTP/json endpoints.

    The chrome-devtools-mcp server exposes CDP over stdio; the simplest portable
    integration is to drive CDP directly via the /json endpoints and the
    Runtime.evaluate protocol. This wrapper implements navigate + evaluate by
    talking to the WebSocket-less HTTP targets and falls back gracefully.
    """

    def __init__(self, devtools_url: str, log: Callable[[str], None]):
        self.url = devtools_url.rstrip("/")
        self.log = log

    def _tabs(self) -> list[dict]:
        import urllib.request

        with urllib.request.urlopen(f"{self.url}/json", timeout=3) as r:
            return json.loads(r.read().decode())

    def scroll_reels(self, source: str) -> list[dict]:
        """Use CDP Runtime.evaluate in the first Instagram tab to extract reels."""
        try:
            import urllib.request, urllib.parse

            tabs = [t for t in self._tabs() if "instagram.com" in t.get("url", "")]
            if not tabs:
                # open a new tab via /json/new
                new_url = InstagramCollector._source_url(source)
                req = urllib.request.Request(
                    f"{self.url}/json/new?{urllib.parse.urlencode({'url': new_url})}"
                )
                with urllib.request.urlopen(req, timeout=5) as r:
                    tab = json.loads(r.read().decode())
            else:
                tab = tabs[0]
            ws = tab.get("webSocketDebuggerUrl")
            if not ws:
                return []
            return self._cdp_extract(ws, source)
        except Exception as e:  # noqa: BLE001
            self.log(f"[devtools] scroll_reels failed: {e}")
            return []

    def _cdp_extract(self, ws_url: str, source: str, scrolls: int = 8) -> list[dict]:
        """Open a CDP WebSocket, navigate, scroll to lazy-load, and scrape reels."""
        try:
            import websocket  # type: ignore
        except ImportError:
            self.log("[devtools] 'websocket' package missing; install websocket-client")
            return []
        try:
            ws = websocket.create_connection(ws_url, timeout=30)
            _id = 0

            def send(method, params):
                nonlocal _id
                _id += 1
                ws.send(json.dumps({"id": _id, "method": method, "params": params}))
                return _id

            def recv():
                while True:
                    msg = json.loads(ws.recv())
                    if "id" in msg:
                        return msg

            send("Page.enable", {})
            send("Runtime.enable", {})
            send("Page.navigate", {"url": InstagramCollector._source_url(source)})
            recv()
            time.sleep(4)
            # scroll to trigger lazy-loading of reels
            scroll_expr = (
                "for(let i=0;i<arguments[0];i++){window.scrollBy(0,2000);}"
            )
            for _ in range(scrolls):
                send("Runtime.evaluate",
                     {"expression": f"window.scrollBy(0,2000)", "returnByValue": True})
                recv()
                time.sleep(self.config.rate_limit_seconds)
            expr = (
                "Array.from(document.querySelectorAll('a[href*=\"/reel/\"],"
                "a[href*=\"/p/\"]')).map(a=>{const h=a.getAttribute('href')||'';"
                "return (h.includes('/reel/')||h.includes('/p/'))"
                "?('https://www.instagram.com'+h):null}).filter(Boolean)"
            )
            send("Runtime.evaluate", {"expression": expr, "returnByValue": True})
            res = recv()
            ws.close()
            root = (res.get("result", {}) or {}).get("result", {}) or {}
            values = root.get("value", []) or []
            return [{"url": u} for u in values]
        except Exception as e:  # noqa: BLE001
            self.log(f"[devtools] cdp_extract failed: {e}")
            return []

    # --- reusable CDP primitives (used by live run + diagnostics) ---
    def cdp_send(self, ws_url: str, method: str, params: dict) -> int:
        import websocket  # type: ignore

        ws = websocket.create_connection(ws_url, timeout=10)
        self._ws = ws
        self._cid = 0
        return self._ws_send(method, params)

    def _ws_send(self, method, params):
        self._cid += 1
        self._ws.send(json.dumps({"id": self._cid, "method": method, "params": params}))
        return self._cid

    def cdp_recv(self) -> dict:
        while True:
            msg = json.loads(self._ws.recv())
            if "id" in msg:
                return msg

    def cdp_eval(self, ws_url: str, expression: str) -> dict:
        """Navigate-free evaluate against an existing tab websocket."""
        try:
            import websocket  # type: ignore

            ws = websocket.create_connection(ws_url, timeout=30)
            cid = 0

            def _send(method, params):
                nonlocal cid
                cid += 1
                ws.send(json.dumps({"id": cid, "method": method, "params": params}))
                return cid

            _send("Runtime.enable", {})
            _send("Runtime.evaluate", {"expression": expression, "returnByValue": True})
            res = None
            while True:
                m = json.loads(ws.recv())
                if "id" in m:
                    res = m
                    break
            ws.close()
            return res or {}
        except Exception as e:  # noqa: BLE001
            self.log(f"[devtools] cdp_eval failed: {e}")
            return {}
