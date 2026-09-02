"""
SkySnailAdapter — creative optimization engine (§9).

Workflow: video/topic -> transcript/context -> thumbnail brief -> 3-5 variants
        -> creative metadata -> experiment record -> CTR/retention -> learning

Goal is generate -> measure -> learn -> improve, not one-off assets.
"""
from __future__ import annotations

import hashlib
import json
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .provider_policy import assert_allowed
from .types import CreativeVariant
from .jobs import GenerationJob, JobStore, input_hash
from .observability import record, AuditLog

ALLOWED_HOSTS = {"api.skysnail.ai", "skysnail.ai", "www.skysnail.ai", "app.skysnail.ai"}

class SkySnailError(RuntimeError):
    def __init__(self, code: str, msg: str, retryable: bool = False):
        super().__init__(f"[{code}] {msg}")
        self.code = code
        self.retryable = retryable

class SkySnailAdapter:
    def __init__(self, api_key: str = "", base_url: str = "https://api.skysnail.ai", timeout_sec: float = 15.0, store: Optional[JobStore] = None, audit: Optional[AuditLog] = None):
        self.api_key = (api_key or "").strip()
        self.base_url = (base_url or "https://api.skysnail.ai").rstrip("/")
        self.timeout_sec = timeout_sec
        self.store = store or JobStore()
        self.audit = audit or AuditLog()
        # variant store (separate file)
        self.variant_path = Path(__file__).resolve().parents[3] / "MBM" / "Artifacts" / "intelligence" / "creative_variants.json"
        self.variant_path.parent.mkdir(parents=True, exist_ok=True)

    def _gate(self) -> None:
        assert_allowed("skysnail", purpose="production")

    def _headers(self) -> Dict[str, str]:
        h: Dict[str, str] = {"User-Agent": "mbm-intelligence/1.0", "Accept": "application/json", "Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def generate_variants(
        self,
        *,
        source_asset_id: str,
        topic: str,
        transcript: str = "",
        count: int = 3,
        platform: str = "youtube",
        experiment_id: Optional[str] = None,
    ) -> List[CreativeVariant]:
        """
        Generate 3-5 thumbnail variants. Returns CreativeVariant[] with
        experiment linkage. If no API key, returns BLOCKED job equivalent
        (zero variants, audit logged) — never fabricates asset URLs.
        """
        self._gate()
        if count < 1 or count > 5:
            count = 3

        exp_id = experiment_id or f"exp_{hashlib.sha256(f'{source_asset_id}{topic}{time.time_ns()}'.encode()).hexdigest()[:10]}"

        if not self.api_key:
            self.audit.append("skysnail.generate", "skysnail", status="blocked", detail={"reason": "no api key", "source": source_asset_id})
            record("skysnail", "blocked", 1)
            return []

        payload = {
            "source_asset_id": source_asset_id,
            "topic": topic,
            "transcript": transcript[:8000],
            "count": count,
            "platform": platform,
            "experiment_id": exp_id,
        }

        # Try live endpoint
        for ep in ("/api/v1/thumbnails", "/api/thumbnails", "/api/generate/thumbnail"):
            url = self.base_url + ep
            host = urllib.parse.urlparse(url).hostname or ""
            if host.lower() not in ALLOWED_HOSTS and "localhost" not in host:
                continue
            body = json.dumps(payload).encode()
            req = urllib.request.Request(url, data=body, headers=self._headers(), method="POST")
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_sec) as res:
                    if res.status in (200, 201, 202):
                        data = json.loads(res.read().decode("utf-8") or "{}")
                        variants = self._normalize_variants(data, source_asset_id, platform, exp_id)
                        self._persist_variants(variants)
                        self.audit.append("skysnail.generate", "skysnail", status="ok", detail={"count": len(variants), "experiment": exp_id})
                        record("skysnail", "requests", 1)
                        record("skysnail", "successes", 1)
                        return variants[:count]
                    if res.status == 404:
                        continue
            except urllib.error.HTTPError as e:
                if e.code in (401, 403):
                    self.audit.append("skysnail.generate", "skysnail", status="failed:AUTH_FAILED", detail={"error": f"HTTP {e.code}"})
                    record("skysnail", "auth_failures", 1)
                    return []
                if e.code == 429:
                    record("skysnail", "rate_limited", 1)
                    time.sleep(1)
                    continue
            except Exception as e:
                if "timed out" in str(e).lower():
                    record("skysnail", "timeouts", 1)
                continue

        self.audit.append("skysnail.generate", "skysnail", status="failed", detail={"reason": "no endpoint succeeded"})
        record("skysnail", "failures", 1)
        return []

    def _normalize_variants(self, data: Any, source_id: str, platform: str, exp_id: str) -> List[CreativeVariant]:
        items: Any = data
        if isinstance(data, dict):
            for key in ("data", "variants", "thumbnails", "items", "results"):
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break
        if not isinstance(items, list):
            return []
        out: List[CreativeVariant] = []
        for idx, raw in enumerate(items):
            if not isinstance(raw, dict):
                continue
            vid = str(raw.get("id") or raw.get("variant_id") or f"var_{idx}_{hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()[:8]}")
            out.append(CreativeVariant(
                variantId=vid,
                experimentId=str(raw.get("experiment_id") or exp_id),
                sourceAssetId=str(raw.get("source_asset_id") or source_id),
                platform=str(raw.get("platform") or platform),
                config=raw.get("config") or {"model": raw.get("model", ""), "template": raw.get("template", "")},
                prompt=raw.get("prompt") or raw.get("brief"),
                assetUrl=raw.get("url") or raw.get("asset_url") or raw.get("image_url"),
                createdAt=datetime.now(timezone.utc).isoformat(),
                status="generated",
            ))
        return out

    def _persist_variants(self, variants: List[CreativeVariant]) -> None:
        try:
            existing: List[Dict[str, Any]] = []
            if self.variant_path.exists():
                existing = json.loads(self.variant_path.read_text(encoding="utf-8"))
                if not isinstance(existing, list):
                    existing = []
        except Exception:
            existing = []
        existing.extend([v.__dict__ for v in variants])
        tmp = self.variant_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(existing, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.variant_path)

    def record_result(self, variant_id: str, *, ctr: Optional[float] = None, views: Optional[int] = None, retention: Optional[float] = None) -> None:
        """Attach measured performance to a variant (experiment closure)."""
        try:
            if not self.variant_path.exists():
                return
            data = json.loads(self.variant_path.read_text(encoding="utf-8"))
            for it in data:
                if it.get("variantId") == variant_id:
                    it["metrics"] = {k: v for k, v in {"ctr": ctr, "views": views, "retention": retention}.items() if v is not None}
                    it["status"] = "measured"
                    break
            tmp = self.variant_path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
            tmp.replace(self.variant_path)
        except Exception:
            pass
