"""collector -- municipal code-violation data collection + classification.

Connectors:
  - Socrata SoQL JSON (Dallas, Plano)
  - ArcGIS REST FeatureServer (Fort Worth, Arlington)

Every connector is injectable via `fetch_json` so tests stay hermetic.

Classification contract (mission Phase 5): every record gets a primary
category + confidence. Categories are never invented - when the signal is
too weak the category is OTHER with a low confidence and the reason is
recorded. REPEAT and LONG_STANDING are computed at the property level by
pipeline.py (they need multiple cases / age), not per-record here.
"""
from __future__ import annotations

import json
import re
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from ..lead_provenance import is_placeholder_phone

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
DEFAULT_TIMEOUT = 15

REGISTRY_PATH = Path(__file__).resolve().parent / "source_registry.json"

# status keywords that mark a case resolved/inactive
INACTIVE_STATUS_KEYWORDS = (
    "closed", "compliant", "resolved", "complete", "dismissed",
    "cancelled", "canceled", "no violation", "duplicate", "archived",
)

CATEGORY_KEYWORDS: dict[str, tuple[float, tuple[str, ...]]] = {
    "VACANT": (0.9, (
        "vacant", "abandoned", "unoccupied", "boarded", "vacant structure",
    )),
    "UNSAFE": (0.9, (
        "unsafe", "fire hazard", "safety hazard", "dangerous", "dilapidated",
    )),
    "STRUCTURAL": (0.85, (
        "structural", "foundation", "roof", "roofing", "exterior wall",
        "collapsing", "cracked wall", "wall damage", "roof damage",
    )),
    "EXTERIOR": (0.8, (
        "exterior", "peeling paint", "paint", "siding", "facade", "fence",
        "boarding", "windows", "broken window", "screen", "gutters",
        "trim", "front porch", "steps", "garage door",
    )),
    "MAINTENANCE": (0.75, (
        "overgrown", "tall grass", "weeds", "debris", "junk", "trash",
        "litter", "garbage", "rubbish", "maintenance", "storage",
        "high grass", "dead vegetation", "unkept", "unkempt", "grass",
        "bushes", "trees", "mosquito", "rodent",
    )),
    "PROPERTY_DERELICT": (0.9, (
        "derelict", "dilapidated building", "condemned", "substandard",
        "blighted", "blight", "substandard building",
    )),
    "DEMOLITION": (0.9, (
        "demolition", "demolish", "raze", "razing",
    )),
}

GENERIC_KEYWORDS = ("code", "violation", "complaint", "notice", "order")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso8601(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def normalize_address(addr: str) -> str:
    """Canonical property address: uppercase, collapsed whitespace."""
    if not addr:
        return ""
    s = re.sub(r"\s+", " ", str(addr).strip()).upper()
    return re.sub(r"^(\d+) ?", r"\1 ", s).strip()


def is_inactive_status(status: str) -> bool:
    s = str(status or "").strip().lower()
    return any(k in s for k in INACTIVE_STATUS_KEYWORDS)


def classify_violation(
    text: str,
    status: str = "",
    opened_iso: str = "",
    now: Optional[datetime] = None,
) -> dict[str, Any]:
    """Classify a single violation record.

    Returns {"category", "classification_confidence", "reason"}.
    """
    text_norm = re.sub(r"[\W_]+", " ", str(text or "").strip().lower())
    now = now or utcnow()

    active = not is_inactive_status(status)

    best_category: Optional[str] = None
    best_confidence = 0.0
    best_reason = ""
    for category, (confidence, kws) in CATEGORY_KEYWORDS.items():
        for kw in kws:
            if kw in text_norm:
                if confidence > best_confidence:
                    best_category = category
                    best_confidence = confidence
                    best_reason = f"keyword '{kw}' in '{text}'"
                break

    if best_category is None and any(g in text_norm for g in GENERIC_KEYWORDS):
        best_category = "OTHER"
        best_confidence = 0.45
        best_reason = f"generic code-violation text in '{text}'"

    if best_category is None:
        best_category = "OTHER"
        best_confidence = 0.2
        best_reason = "no discriminating keywords; needs verification"

    # status is a low-confidence signal only; it never overrides category
    if not active:
        best_confidence = max(best_confidence, 0.5)
        best_confidence = min(best_confidence, 1.0)

    if opened_iso:
        try:
            opened = datetime.fromisoformat(str(opened_iso).replace("Z", "+00:00"))
            if opened.tzinfo is None:
                opened = opened.replace(tzinfo=timezone.utc)
            age_days = (now - opened).days
        except ValueError:
            age_days = None
    else:
        age_days = None

    return {
        "category": best_category,
        "classification_confidence": round(best_confidence, 3),
        "reason": best_reason,
        "active": active,
        "age_days": age_days,
        "status_raw": str(status or ""),
        "text_raw": str(text or ""),
    }


def _default_fetch(url: str, timeout: int = DEFAULT_TIMEOUT) -> Any:
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode())


class SocrataSource:
    """Socrata SoQL JSON source (Dallas, Plano)."""

    def __init__(self, name: str, cfg: dict, fetch_json: Callable[..., Any] = _default_fetch):
        self.name = name
        self.cfg = cfg
        self.fields = cfg.get("fields", {})
        self.conn = cfg.get("connector", {})
        self.fetch_json = fetch_json

    def _record_fields(self) -> list[str]:
        out: list[str] = []
        for key in ("address_field", "case_id_field", "type_field", "status_field",
                    "department_field", "created_date_field", "updated_date_field"):
            val = self.fields.get(key)
            if val:
                out.append(val)
        return out

    def query_url(self, since_iso: str = "", days_back: int = 45) -> str:
        base = self.cfg["api_url"].rstrip("/")
        if not base.endswith(".json"):
            base += ".json"
        date_f = self.fields.get("created_date_field")
        update_f = self.fields.get("updated_date_field")
        where_parts: list[str] = []
        if since_iso:
            if date_f:
                where_parts.append(f"{date_f} >= '{since_iso}'")
            if update_f and self.conn.get("update_field"):
                where_parts.append(f"{update_f} >= '{since_iso}'")
        else:
            from datetime import timedelta
            cutoff = utcnow() - timedelta(days=days_back)
            start = iso8601(cutoff)
            if date_f:
                where_parts.append(f"{date_f} >= '{start}'")
        where = " OR ".join(where_parts)
        params = {"$limit": "5000", "$order": f"{date_f or '_id'} DESC"}
        if where:
            params["$where"] = where
        return base + "?" + urllib.parse.urlencode(params)

    def _matches_filters(self, rec: dict) -> bool:
        conn = self.conn
        dep_f = self.fields.get("department_field")
        dep = str(rec.get(dep_f, "") or "") if dep_f else ""
        type_f = self.fields.get("type_field")
        typ = str(rec.get(type_f, "") or "") if type_f else ""
        deps = conn.get("department_filter") or []
        types = conn.get("type_filter") or []
        if deps:
            if not any(d.lower() in dep.lower() for d in deps):
                return False
        if types:
            if not any(t.lower() in typ.lower() for t in types):
                return False
        return True

    def collect(self, since_iso: str = "", days_back: int = 45) -> list[dict]:
        url = self.query_url(since_iso=since_iso, days_back=days_back)
        rows = self.fetch_json(url) or []
        out = []
        for rec in rows:
            if not self._matches_filters(rec):
                continue
            out.append(self._to_raw(rec))
        return out

    def _to_raw(self, rec: dict) -> dict:
        f = self.fields
        return {
            "source": self.cfg["market"],
            "source_name": self.cfg["source_name"],
            "dataset_url": self.cfg["dataset_url"],
            "address": normalize_address(rec.get(f.get("address_field", "")) or ""),
            "case_id": str(rec.get(f.get("case_id_field", "")) or "").strip() if f.get("case_id_field") else "",
            "violation_type": str(rec.get(f.get("type_field", "")) or "").strip(),
            "status": str(rec.get(f.get("status_field", "")) or "").strip(),
            "department": str(rec.get(f.get("department_field", "")) or "").strip() if f.get("department_field") else "",
            "opened_iso": str(rec.get(f.get("created_date_field", "")) or "").strip() if f.get("created_date_field") else "",
            "updated_iso": str(rec.get(f.get("updated_date_field", "")) or "").strip() if f.get("updated_date_field") else "",
            "city": self.cfg["market"].split(",")[0].strip(),
            "state": self.cfg["state"],
            "county": self.cfg["county"],
            "parcel_id": str(rec.get(f.get("parcel_field", "")) or "").strip() if f.get("parcel_field") else "",
        }


class ArcGisSource:
    """ArcGIS REST FeatureServer source (Fort Worth, Arlington)."""

    def __init__(self, name: str, cfg: dict, fetch_json: Callable[..., Any] = _default_fetch):
        self.name = name
        self.cfg = cfg
        self.fields = cfg.get("fields", {})
        self.conn = cfg.get("connector", {})
        self.fetch_json = fetch_json
        self.timeout = DEFAULT_TIMEOUT

    def _endpoint(self) -> str:
        return self.cfg["api_url"]

    def query_url(self, where: str = "1=1", result_offset: int = 0) -> str:
        conn = self.conn
        out_fields = self._out_fields()
        date_f = conn.get("incremental_field")
        order = f"{date_f} DESC" if date_f else "ObjectID ASC"
        params = {
            "where": where,
            "outFields": out_fields,
            "returnGeometry": "false",
            "resultRecordCount": "1000",
            "resultOffset": str(result_offset),
            "orderByFields": order,
            "f": "json",
        }
        return self._endpoint().rstrip("/") + "/query?" + urllib.parse.urlencode(params)

    def _out_fields(self) -> str:
        out: list[str] = []
        for key in ("address_field", "case_id_field", "type_field", "status_field",
                    "created_date_field", "updated_date_field", "parcel_field",
                    "property_type_field", "closed_date_field", "violation_id_field",
                    "city_field", "state_field"):
            val = self.fields.get(key)
            if val:
                out.append(val)
        return ",".join(dict.fromkeys(out))

    def _since_epoch(self, since_iso: str, days_back: int) -> int:
        if since_iso:
            dt = datetime.fromisoformat(since_iso.replace("Z", "+00:00"))
            return int(dt.timestamp() * 1000)
        from datetime import timedelta
        cutoff = utcnow() - timedelta(days=days_back)
        return int(cutoff.timestamp() * 1000)

    def _unwrap_features(self, payload: Any) -> list[dict]:
        """ArcGIS REST returns {fields:[...], features:[{attributes:{...}}]}. Unwrap to rows."""
        if isinstance(payload, dict):
            feats = payload.get("features")
            if isinstance(feats, list):
                rows = []
                for f in feats:
                    attrs = f.get("attributes") if isinstance(f, dict) else None
                    if isinstance(attrs, dict):
                        rows.append(attrs)
                return rows
            return []
        return payload or []

    def collect(self, since_iso: str = "", days_back: int = 45, max_pages: int = 20) -> list[dict]:
        conn = self.conn
        date_f = conn.get("incremental_field")
        where = "1=1"
        if date_f:
            epoch = self._since_epoch(since_iso, days_back)
            where = f"{date_f} >= {epoch}"
        out: list[dict] = []
        for offset in range(0, max_pages * 1000, 1000):
            url = self.query_url(where=where, result_offset=offset)
            payload = self.fetch_json(url)
            rows = self._unwrap_features(payload)
            if not rows:
                break
            for rec in rows:
                out.append(self._to_raw(rec))
            if len(rows) < 1000:
                break
        return out

    def _to_raw(self, rec: dict) -> dict:
        f = self.fields
        opened = rec.get(f.get("created_date_field")) if f.get("created_date_field") else None
        opened_iso = ""
        if opened not in (None, ""):
            try:
                ms = int(opened)
                opened_iso = datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
            except (ValueError, TypeError, OSError):
                opened_iso = str(opened)
        case_id = rec.get(f.get("case_id_field")) if f.get("case_id_field") else None
        return {
            "source": self.cfg["market"],
            "source_name": self.cfg["source_name"],
            "dataset_url": self.cfg["dataset_url"],
            "address": normalize_address(rec.get(f.get("address_field")) or ""),
            "case_id": str(case_id).strip() if case_id not in (None, "") else "",
            "violation_type": str(rec.get(f.get("type_field")) or "").strip() if f.get("type_field") else "",
            "status": str(rec.get(f.get("status_field")) or "").strip() if f.get("status_field") else "",
            "opened_iso": opened_iso,
            "updated_iso": "",
            "city": self.cfg["market"].split(",")[0].strip(),
            "state": self.cfg["state"],
            "county": self.cfg["county"],
            "parcel_id": str(rec.get(f.get("parcel_field")) or "").strip() if f.get("parcel_field") else "",
            "closed_date": str(rec.get(f.get("closed_date_field")) or "").strip() if f.get("closed_date_field") else "",
        }


SOURCE_CONNECTORS: dict[str, type] = {
    "socrata": SocrataSource,
    "arcgis": ArcGisSource,
}


def load_source_registry(path: Optional[Path] = None) -> dict[str, Any]:
    p = path or REGISTRY_PATH
    with open(p, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    return data


def active_sources(registry: dict[str, Any]) -> dict[str, dict]:
    return {
        name: cfg for name, cfg in registry.get("sources", {}).items()
        if cfg.get("active")
    }


def collect_source(
    name: str,
    cfg: dict,
    fetch_json: Callable[..., Any] = _default_fetch,
    since_iso: str = "",
    days_back: int = 45,
    max_pages: int = 20,
) -> list[dict]:
    """Collect raw violations from one registry source via its connector."""
    conn = cfg.get("connector", {})
    ctype = conn.get("type") or cfg.get("source_type", "")
    cls = SOURCE_CONNECTORS.get(ctype)
    if cls is None:
        raise ValueError(f"no connector for source type '{ctype}' ({name})")
    connector = cls(name, cfg, fetch_json=fetch_json)
    return connector.collect(
        since_iso=since_iso,
        days_back=days_back,
        **({"max_pages": max_pages} if isinstance(connector, ArcGisSource) else {}),
    )


def enrich_violation(rec: dict) -> dict:
    """Add classification + phone sanity fields to a raw violation record."""
    out = dict(rec)
    cls = classify_violation(
        rec.get("violation_type", ""),
        status=rec.get("status", ""),
        opened_iso=rec.get("opened_iso", ""),
    )
    out["category"] = cls["category"]
    out["classification_confidence"] = cls["classification_confidence"]
    out["classification_reason"] = cls["reason"]
    out["active"] = cls["active"]
    out["age_days"] = cls["age_days"]
    return out


def record_key(rec: dict) -> str:
    """Dedup key for one violation case (source + case id, else composite)."""
    src = rec.get("source", "")
    case_id = rec.get("case_id", "")
    if case_id:
        return f"{src}::{case_id}"
    addr = rec.get("address", "")
    typ = rec.get("violation_type", "")
    opened = rec.get("opened_iso", "") or rec.get("closed_date", "")
    return f"{src}::{addr}::{typ}::{opened}"


def is_rejected_violation(rec: dict) -> bool:
    """Records that must never reach the pipeline (no address / no signal)."""
    if not rec.get("address"):
        return True
    if rec.get("phone") and is_placeholder_phone(str(rec.get("phone"))):
        return True
    return False
