"""
AnderroAdapter — monetization intelligence (§7).

Never hardcodes rates (e.g. "50% recurring"). Treats commission/rate
as live data. Returns NOT_VERIFIED / BLOCKED instead of fabricating.

Normalization target:
  AffiliateOffer { offerId, merchant*, vertical, commissionRate, commissionType,
                   recurring, payoutTerms, cookieWindowDays, allowedChannels,
                   restrictions, sourceUrl, verifiedAt, confidence, status }
"""
from __future__ import annotations

import json
import time
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .provider_policy import assert_allowed
from .types import AffiliateOffer
from .observability import record, AuditLog

ALLOWED_HOSTS = {"anderro.com", "api.anderro.com", "www.anderro.com"}

def _is_allowed(url: str) -> bool:
    try:
        import urllib.parse as _u
        host = _u.urlparse(url).hostname or ""
        return host.lower() in ALLOWED_HOSTS
    except Exception:
        return False

MAX_BYTES = 1 * 1024 * 1024

class AnderroError(RuntimeError):
    def __init__(self, code: str, msg: str, retryable: bool = False):
        super().__init__(f"[{code}] {msg}")
        self.code = code
        self.retryable = retryable

class AnderroAdapter:
    """
    Live Anderro marketplace client.

    NOTE: Anderro's public marketplace currently serves HTML; there is no
    stable public JSON API documented for external consumption. The adapter
    therefore:
      - enforces allow_pending_verification gate
      - attempts REST endpoints if ANDERRO_API_KEY / ANDERRO_BASE_URL provided
      - otherwise returns NOT_VERIFIED with clear provenance (never invents rates)
    """
    def __init__(self, api_key: str = "", base_url: str = "https://anderro.com", timeout_sec: float = 10.0, audit: Optional[AuditLog] = None):
        self.api_key = (api_key or "").strip()
        self.base_url = (base_url or "https://anderro.com").rstrip("/")
        self.timeout_sec = timeout_sec
        self.audit = audit or AuditLog()

    def _gate(self) -> None:
        assert_allowed("anderro", purpose="production")

    def _headers(self) -> Dict[str, str]:
        h = {"User-Agent": "mbm-intelligence/1.0", "Accept": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def list_offers(self, *, vertical: str = "", limit: int = 20, force_live: bool = False) -> List[AffiliateOffer]:
        """
        Fetch affiliate offers. If no API is configured, returns NOT_VERIFIED
        placeholders that signal the caller to treat rates as unverified.
        Never fabricates a commissionRate.
        """
        self._gate()
        if not self.api_key:
            # No credential path -> cannot verify rates live.
            self.audit.append("anderro.list_offers", "anderro", status="not_verified", detail={"reason": "no ANDERRO_API_KEY"})
            return [
                AffiliateOffer(
                    offerId="anderro_unverified_placeholder",
                    merchantName="Anderro Marketplace",
                    vertical=vertical or "unknown",
                    commissionRate=None,
                    commissionType=None,
                    recurring=None,
                    sourceUrl=self.base_url,
                    verifiedAt=datetime.now(timezone.utc).isoformat(),
                    confidence=0.0,
                    status="NOT_VERIFIED",
                )
            ]

        # Live path — try plausible endpoints with bounded retries
        endpoints = ["/api/offers", "/api/v1/offers", "/api/marketplace/offers", "/api/affiliate/offers"]
        last_err: Optional[Exception] = None
        for ep in endpoints:
            try:
                offers = self._fetch_offers(ep, vertical=vertical, limit=limit)
                if offers is not None:
                    self.audit.append("anderro.list_offers", "anderro", status="ok", detail={"endpoint": ep, "count": len(offers)})
                    return offers
            except AnderroError as e:
                if e.code in ("AUTH_FAILED", "BLOCKED"):
                    raise
                last_err = e
                if not e.retryable:
                    break
                time.sleep(1)
            except Exception as e:
                last_err = e
                time.sleep(1)

        # Blocked or unreachable -> return BLOCKED marker (consistent with §7: return BLOCKED not fabricated data)
        self.audit.append("anderro.list_offers", "anderro", status="blocked", detail={"error": str(last_err)[:500] if last_err else "unknown"})
        return [
            AffiliateOffer(
                offerId="anderro_blocked",
                merchantName="Anderro",
                vertical=vertical or "unknown",
                sourceUrl=self.base_url,
                verifiedAt=datetime.now(timezone.utc).isoformat(),
                confidence=0.0,
                status="BLOCKED",
            )
        ]

    def _fetch_offers(self, endpoint: str, *, vertical: str, limit: int) -> Optional[List[AffiliateOffer]]:
        url = f"{self.base_url}{endpoint}"
        params = {}
        if vertical:
            params["vertical"] = vertical
        if limit:
            params["limit"] = str(limit)
        if params:
            url += "?" + urllib.parse.urlencode(params)
        # SSRF guard
        import urllib.parse as _u
        host = _u.urlparse(url).hostname or ""
        if host.lower() not in ALLOWED_HOSTS and "localhost" not in host:
            raise AnderroError("BLOCKED", f"URL not allowlisted: {url}")

        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as res:
                if res.status == 404:
                    return None  # try next endpoint
                raw = res.read(MAX_BYTES + 1)
                if len(raw) > MAX_BYTES:
                    raise AnderroError("VALIDATION_FAILED", "payload too large")
                data = json.loads(raw.decode("utf-8", errors="replace")) if raw else {}
                record("anderro", "requests", 1, latency_ms=(time.time() - t0) * 1000)
                return self._normalize_offers(data)
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                raise AnderroError("AUTH_FAILED", f"HTTP {e.code}")
            if e.code == 429:
                raise AnderroError("RATE_LIMITED", "HTTP 429", retryable=True)
            if 500 <= e.code < 600:
                raise AnderroError("TRANSIENT", f"HTTP {e.code}", retryable=True)
            raise AnderroError("TRANSIENT", f"HTTP {e.code}", retryable=False)
        except Exception as e:
            if "timed out" in str(e).lower():
                raise AnderroError("TIMEOUT", str(e), retryable=True)
            raise AnderroError("TRANSIENT", str(e), retryable=True)

    def _normalize_offers(self, data: Any) -> List[AffiliateOffer]:
        now = datetime.now(timezone.utc).isoformat()
        items: Any = data
        if isinstance(data, dict):
            for key in ("data", "offers", "items", "results", "marketplace"):
                if key in data and isinstance(data[key], list):
                    items = data[key]
                    break
        if not isinstance(items, list):
            return []
        out: List[AffiliateOffer] = []
        for raw in items:
            if not isinstance(raw, dict):
                continue
            oid = str(raw.get("id") or raw.get("offerId") or raw.get("offer_id") or raw.get("program_id") or "").strip()
            if not oid:
                continue
            # Never invent rate: only set if provider returned a numeric rate
            rate: Optional[float] = None
            for k in ("commissionRate", "commission_rate", "commission", "rate", "payout_rate"):
                v = raw.get(k)
                if v is not None:
                    try:
                        # handle "30%" strings
                        if isinstance(v, str) and "%" in v:
                            rate = float(v.strip().strip("%")) / 100.0
                        else:
                            rate = float(v)
                            if rate > 1:
                                rate = rate / 100.0
                        break
                    except Exception:
                        continue
            # recurring: only set if explicit
            rec = raw.get("recurring")
            if isinstance(rec, str):
                rec = rec.lower() in ("1", "true", "yes", "recurring")
            out.append(AffiliateOffer(
                offerId=oid,
                merchantId=str(raw.get("merchantId") or raw.get("merchant_id") or raw.get("advertiser_id") or "") or None,
                merchantName=str(raw.get("merchantName") or raw.get("merchant_name") or raw.get("advertiser") or raw.get("program_name") or "") or None,
                vertical=str(raw.get("vertical") or raw.get("category") or raw.get("niche") or "") or None,
                commissionRate=rate,
                commissionType=str(raw.get("commissionType") or raw.get("commission_type") or raw.get("payout_type") or "") or None,
                recurring=bool(rec) if rec is not None else None,
                payoutTerms=str(raw.get("payoutTerms") or raw.get("payout_terms") or "") or None,
                cookieWindowDays=int(raw.get("cookieWindowDays") or raw.get("cookie_days") or 0) or None,
                allowedChannels=[str(x) for x in (raw.get("allowedChannels") or raw.get("allowed_channels") or []) if str(x).strip()][:10],
                restrictions=[str(x) for x in (raw.get("restrictions") or []) if str(x).strip()][:10],
                sourceUrl=str(raw.get("url") or raw.get("sourceUrl") or self.base_url) or None,
                verifiedAt=now,
                confidence=1.0 if rate is not None else 0.0,
                status="VERIFIED" if rate is not None else "NOT_VERIFIED",
            ))
        return out

    def get_offer(self, offer_id: str) -> AffiliateOffer:
        """Fetch single offer; NOT_VERIFIED if unavailable."""
        self._gate()
        offers = self.list_offers(limit=50)
        for o in offers:
            if o.offerId == offer_id:
                return o
        return AffiliateOffer(
            offerId=offer_id,
            sourceUrl=self.base_url,
            verifiedAt=datetime.now(timezone.utc).isoformat(),
            confidence=0.0,
            status="NOT_VERIFIED",
        )
