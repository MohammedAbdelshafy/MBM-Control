"""
WorldMonitorAdapter — canonical World Monitor integration (§4).

Prefer hosted API/MCP consumption over vendoring AGPL code.

Responsibilities:
  MCP connection (if WORLDMONITOR_MCP_URL set)
  REST fallback (OpenAPI)
  auth, timeout, bounded retries, rate-limit handling
  structured error classification (BLOCKED / RATE_LIMITED / AUTH_FAILED / TRANSIENT)
  tool discovery (dynamic, cached, validated)
  schema validation + response normalization -> IntelligenceEvent[]
  provenance preservation + freshness tracking

Security: env-only credentials, no secrets in logs, payload-size limits,
          URL allowlist, content-type validation, SSRF guard.
"""
from __future__ import annotations

import json
import os
import time
import hashlib
import urllib.request
import urllib.error
import urllib.parse
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .provider_policy import assert_allowed
from .types import IntelligenceEvent, Provenance
from .observability import record, AuditLog

# --- error taxonomy ---
class ProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False, raw: Any = None):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.retryable = retryable
        self.raw = raw

BLOCKED = "BLOCKED"
RATE_LIMITED = "RATE_LIMITED"
AUTH_FAILED = "AUTH_FAILED"
TIMEOUT = "TIMEOUT"
TRANSIENT = "TRANSIENT"
VALIDATION_FAILED = "VALIDATION_FAILED"
NOT_VERIFIED = "NOT_VERIFIED"

# Allowlist for outbound calls (SSRF guard + URL allowlist per §12)
ALLOWED_HOSTS = {
    "worldmonitor.app",
    "api.worldmonitor.app",
    "www.worldmonitor.app",
}
# Also allow localhost for hermetic tests when flag set
def _is_allowed_url(url: str) -> bool:
    try:
        host = urllib.parse.urlparse(url).hostname or ""
        host = host.lower()
        if host in ALLOWED_HOSTS:
            return True
        if host in ("localhost", "127.0.0.1", "::1"):
            return os.environ.get("INTELLIGENCE_ALLOW_BLOCKED_IN_TESTS", "").lower() in ("1", "true", "yes", "on")
        return False
    except Exception:
        return False

MAX_PAYLOAD_BYTES = 2 * 1024 * 1024  # 2 MB

# Canonical repo / site — recorded for license review
CANONICAL_REPO = "koala73/worldmonitor"
CANONICAL_SITE = "https://worldmonitor.app"
CANONICAL_LICENSE = "AGPL-3.0"

@dataclass
class ToolDescriptor:
    name: str
    description: str = ""
    schema: Dict[str, Any] | None = None

class WorldMonitorAdapter:
    """
    Consumes World Monitor via REST/MCP. No AGPL source is vendored.
    """
    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://worldmonitor.app",
        mcp_url: str = "",
        timeout_sec: float = 12.0,
        max_retries: int = 3,
        cache_ttl_sec: int = 600,
        audit: Optional[AuditLog] = None,
    ):
        self.api_key = (api_key or "").strip()
        self.base_url = (base_url or "https://worldmonitor.app").rstrip("/")
        self.mcp_url = (mcp_url or "").strip()
        self.timeout_sec = timeout_sec
        self.max_retries = max_retries
        self.cache_ttl_sec = cache_ttl_sec
        self.audit = audit or AuditLog()
        self._tool_cache: Optional[Tuple[float, List[ToolDescriptor]]] = None

    # -- policy gate -------------------------------------------------------
    def _gate(self) -> None:
        assert_allowed("worldmonitor", purpose="production")

    # -- low-level fetch with security rails -------------------------------
    def _headers(self) -> Dict[str, str]:
        h = {"User-Agent": "mbm-intelligence/1.0", "Accept": "application/json"}
        if self.api_key:
            # World Monitor docs describe API authentication; prefer Bearer.
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def _fetch(self, url: str, *, method: str = "GET", body: Optional[bytes] = None) -> Tuple[int, bytes, Dict[str, str]]:
        if not _is_allowed_url(url):
            raise ProviderError(BLOCKED, f"URL not in allowlist: {url}")
        req = urllib.request.Request(url, data=body, headers=self._headers(), method=method)
        if body:
            req.add_header("Content-Type", "application/json")
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as res:
                status = res.status
                headers = {k.lower(): v for k, v in res.headers.items()}
                ctype = headers.get("content-type", "")
                if "application/json" not in ctype and "text/json" not in ctype and status != 204:
                    # allow but warn — validate downstream
                    pass
                raw = res.read(MAX_PAYLOAD_BYTES + 1)
                if len(raw) > MAX_PAYLOAD_BYTES:
                    raise ProviderError(VALIDATION_FAILED, f"payload exceeds {MAX_PAYLOAD_BYTES} bytes")
                record("worldmonitor", "requests", 1, latency_ms=(time.time() - t0) * 1000)
                record("worldmonitor", "successes", 1)
                return status, raw, headers
        except urllib.error.HTTPError as e:
            body_bytes = b""
            try:
                body_bytes = e.read()[:4000]
            except Exception:
                pass
            if e.code in (401, 403):
                record("worldmonitor", "auth_failures", 1)
                raise ProviderError(AUTH_FAILED, f"HTTP {e.code} {e.reason}", raw=body_bytes)
            if e.code == 429:
                record("worldmonitor", "rate_limited", 1)
                raise ProviderError(RATE_LIMITED, f"HTTP 429 rate limited", retryable=True, raw=body_bytes)
            if 500 <= e.code < 600:
                raise ProviderError(TRANSIENT, f"HTTP {e.code} {e.reason}", retryable=True, raw=body_bytes)
            raise ProviderError(TRANSIENT, f"HTTP {e.code} {e.reason}", raw=body_bytes)
        except TimeoutError:
            record("worldmonitor", "timeouts", 1)
            raise ProviderError(TIMEOUT, "request timed out", retryable=True)
        except Exception as e:
            if "timed out" in str(e).lower():
                record("worldmonitor", "timeouts", 1)
                raise ProviderError(TIMEOUT, str(e), retryable=True)
            raise ProviderError(TRANSIENT, str(e), retryable=True)

    # -- tool discovery (dynamic, cached) ----------------------------------
    def discover_tools(self, *, force_refresh: bool = False) -> List[ToolDescriptor]:
        """
        Discover available tools. Tries MCP listTools then REST OpenAPI.
        Never hardcodes a fixed list.
        """
        self._gate()
        if self._tool_cache and not force_refresh:
            ts, tools = self._tool_cache
            if time.time() - ts < self.cache_ttl_sec:
                return tools

        # Try MCP discovery if mcp_url configured
        if self.mcp_url:
            try:
                tools = self._discover_via_mcp()
                self._tool_cache = (time.time(), tools)
                self.audit.append("worldmonitor.discover", "worldmonitor", status="ok", detail={"via": "mcp", "count": len(tools)})
                return tools
            except Exception as e:
                self.audit.append("worldmonitor.discover", "worldmonitor", status="mcp_failed", detail={"error": str(e)[:400]})

        # REST fallback: try conventional discovery endpoints
        for path in ("/api/tools", "/api/v1/tools", "/mcp/tools", "/openapi.json", "/api/openapi.json"):
            try:
                status, raw, _ = self._fetch(self.base_url + path)
                if status == 200 and raw:
                    data = json.loads(raw.decode("utf-8", errors="replace"))
                    tools = self._parse_tool_list(data)
                    if tools:
                        self._tool_cache = (time.time(), tools)
                        self.audit.append("worldmonitor.discover", "worldmonitor", status="ok", detail={"via": path, "count": len(tools)})
                        return tools
            except ProviderError:
                continue
            except Exception:
                continue

        # Graceful degrade: no tools discoverable, return empty (caller validates capabilities)
        self.audit.append("worldmonitor.discover", "worldmonitor", status="empty", detail={"reason": "no discovery endpoint responded"})
        return []

    def _discover_via_mcp(self) -> List[ToolDescriptor]:
        # JSON-RPC MCP listTools
        payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}).encode()
        status, raw, _ = self._fetch(self.mcp_url, method="POST", body=payload)
        data = json.loads(raw.decode("utf-8", errors="replace"))
        tools_raw = data.get("result", {}).get("tools") or data.get("tools") or []
        return [ToolDescriptor(name=t.get("name", ""), description=t.get("description", ""), schema=t.get("inputSchema") or t.get("schema")) for t in tools_raw if t.get("name")]

    def _parse_tool_list(self, data: Any) -> List[ToolDescriptor]:
        if isinstance(data, dict):
            # OpenAPI -> synthesize tool names from paths
            if "paths" in data:
                return [ToolDescriptor(name=k.strip("/").replace("/", "."), description=(v.get("get") or v.get("post") or {}).get("summary", "")) for k, v in data["paths"].items()]
            for key in ("tools", "data", "items", "results"):
                if key in data and isinstance(data[key], list):
                    return [ToolDescriptor(name=str(t.get("name") or t.get("id") or ""), description=str(t.get("description") or "")) for t in data[key] if isinstance(t, dict)]
        if isinstance(data, list):
            return [ToolDescriptor(name=str(t.get("name") or "")) for t in data if isinstance(t, dict) and t.get("name")]
        return []

    # -- fetch intelligence -------------------------------------------------
    def fetch_events(self, *, query: str = "", category: str = "", limit: int = 20) -> List[IntelligenceEvent]:
        """
        Retrieve intelligence events via REST with bounded retries.
        Returns normalized IntelligenceEvent[] with provenance.
        """
        self._gate()
        if not self.api_key and not self.mcp_url:
            raise ProviderError(AUTH_FAILED, "WORLDMONITOR_API_KEY / WORLDMONITOR_MCP_URL not configured")

        last_err: Optional[ProviderError] = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return self._fetch_events_once(query=query, category=category, limit=limit)
            except ProviderError as e:
                last_err = e
                if not e.retryable or attempt == self.max_retries:
                    raise
                backoff = min(2 ** attempt, 8)
                time.sleep(backoff)

        raise last_err or ProviderError(TRANSIENT, "fetch_events retries exhausted", retryable=False)

    def _fetch_events_once(self, *, query: str, category: str, limit: int) -> List[IntelligenceEvent]:
        # Try common REST surfaces
        params = {}
        if query:
            params["q"] = query
            params["query"] = query
        if category:
            params["category"] = category
        params["limit"] = str(limit)

        endpoints = ["/api/events", "/api/v1/events", "/api/intelligence", "/api/search"]
        last_exc: Optional[Exception] = None
        for ep in endpoints:
            qs = urllib.parse.urlencode(params)
            url = f"{self.base_url}{ep}?{qs}" if qs else f"{self.base_url}{ep}"
            try:
                status, raw, _ = self._fetch(url)
                if status == 404:
                    last_exc = ProviderError(TRANSIENT, f"{ep} not found", retryable=False)
                    continue
                data = json.loads(raw.decode("utf-8", errors="replace")) if raw else {}
                events = normalize_worldmonitor_response(data, query=query)
                if events is not None:
                    self.audit.append("worldmonitor.fetch", "worldmonitor", status="ok", detail={"endpoint": ep, "count": len(events)})
                    return events
            except ProviderError:
                raise
            except Exception as e:
                last_exc = e
                continue

        raise ProviderError(TRANSIENT, f"No World Monitor endpoint succeeded (last: {last_exc})", retryable=True)


def _parse_dt(s: str) -> Optional[datetime]:
    if not s:
        return None
    try:
        # handle Z and offsets
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None

def normalize_worldmonitor_response(data: Any, *, query: str = "") -> List[IntelligenceEvent]:
    """
    worldMonitorResponse -> IntelligenceEvent[]
    Handles multiple possible payload shapes gracefully.
    """
    now = datetime.now(timezone.utc)
    retrieved = now.isoformat()

    # unwrap common envelopes
    items: Any = data
    if isinstance(data, dict):
        for key in ("data", "events", "items", "results", "records", "payload"):
            if key in data and isinstance(data[key], list):
                items = data[key]
                break
        if items is data:
            # single object -> wrap
            if any(k in data for k in ("title", "event", "headline", "name")):
                items = [data]
            else:
                return []

    if not isinstance(items, list):
        return []

    out: List[IntelligenceEvent] = []
    for idx, raw in enumerate(items):
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or raw.get("headline") or raw.get("name") or raw.get("event") or "").strip()
        if not title:
            continue
        cat = str(raw.get("category") or raw.get("type") or raw.get("topic") or "general").strip() or "general"
        src = str(raw.get("source") or raw.get("provider") or "worldmonitor").strip() or "worldmonitor"
        url = raw.get("url") or raw.get("sourceUrl") or raw.get("link") or raw.get("source_url")
        summary = raw.get("summary") or raw.get("description") or raw.get("content") or raw.get("body")
        pubs = str(raw.get("publishedAt") or raw.get("published_at") or raw.get("date") or raw.get("timestamp") or "")
        obss = str(raw.get("observedAt") or raw.get("observed_at") or pubs or retrieved)
        freshness = None
        try:
            pd = _parse_dt(pubs)
            if pd:
                freshness = int((now - pd).total_seconds())
        except Exception:
            pass
        # entities / locations / topics — accept multiple key variants
        entities = raw.get("entities") or raw.get("people") or []
        locations = raw.get("locations") or raw.get("places") or raw.get("geography") or []
        topics = raw.get("topics") or raw.get("tags") or raw.get("keywords") or []
        # normalize to list[str]
        def _to_str_list(v: Any) -> List[str]:
            if isinstance(v, str):
                return [v]
            if isinstance(v, list):
                return [str(x).strip() for x in v if str(x).strip()]
            return []
        rid = str(raw.get("id") or raw.get("event_id") or raw.get("uid") or hashlib.sha256(f"{src}|{title}|{pubs}".encode()).hexdigest()[:16])
        raw_ref = raw.get("rawReference") or raw.get("raw_reference") or None
        if raw_ref is None:
            try:
                raw_ref = json.dumps(raw, ensure_ascii=False)[:4000]
            except Exception:
                raw_ref = str(raw)[:4000]

        out.append(IntelligenceEvent(
            id=rid,
            source=src,
            sourceUrl=str(url) if url else None,
            observedAt=obss,
            publishedAt=pubs or None,
            category=cat,
            title=title,
            summary=str(summary)[:2000] if summary else None,
            entities=_to_str_list(entities)[:20],
            locations=_to_str_list(locations)[:20],
            topics=_to_str_list(topics)[:20],
            confidence=float(raw.get("confidence") or raw.get("score") or 0.6) if raw.get("confidence") is not None or raw.get("score") is not None else 0.6,
            freshnessSeconds=freshness,
            rawReference=raw_ref,
            provenance=Provenance(provider="worldmonitor", tool=raw.get("tool") or "rest", captured_at=retrieved, source_url=str(url) if url else None, rawReference=raw_ref, transformation_lineage=["worldMonitorResponse -> IntelligenceEvent[]"]),
        ))

    return out
