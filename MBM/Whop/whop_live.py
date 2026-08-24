"""
whop_live.py — Live Whop API truth layer with snapshot protection
=================================================================
Single module responsible for pulling the REAL state of the Whop account,
classifying every response honestly, and never letting a failed API call
destroy the last known-good revenue state.

ROOT CAUSE FIX (2026-08-24, verified against the live API):
    GET /api/v1/memberships?account_id=biz_UxlhGUdO9TpGb0
        -> 400 {"error":{"type":"bad_request","message":"You are not
           authorized - ensure that you have access to this resource"}}
    GET /api/v2/memberships?company_id=biz_UxlhGUdO9TpGb0
        -> 200 {"data":[], "total_count":0}
    The memberships endpoint scopes by ``company_id`` (same parameter the
    /products endpoint already used successfully). Passing ``account_id``
    produced an unscoped request, which Whop rejects as unauthorized.
    With the fixed parameter the account verifiably has ZERO memberships:
    the "0" is now VERIFIED, not inferred from product member_count.

Snapshot states (explicit, mutually exclusive):
    LIVE_VALID     every endpoint succeeded this sync
    LIVE_PARTIAL   some endpoints succeeded, some failed (good parts kept)
    STALE_VALID    reporting a previously-verified value because the fresh
                   call failed (value labelled stale + reason)
    FAILED         all endpoints failed; prior good data preserved untouched
    UNAVAILABLE    no snapshot has ever been captured

Observability: every HTTP call appends to logs/whop_sync_health.jsonl with
timestamp/account_id/endpoint/http_status/latency/records/snapshot_status/
error. Secrets are NEVER logged.

This module is network-free when imported; all I/O happens in sync_live().
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
REPO_ROOT = BASE_DIR.parent.parent

SNAPSHOT_FILE = LOGS_DIR / "whop_revenue.json"
SYNC_HEALTH_LOG = LOGS_DIR / "whop_sync_health.jsonl"

# Explicit snapshot lifecycle states.
LIVE_VALID = "LIVE_VALID"
LIVE_PARTIAL = "LIVE_PARTIAL"
STALE_VALID = "STALE_VALID"
FAILED = "FAILED"
UNAVAILABLE = "UNAVAILABLE"
SNAPSHOT_STATES = (LIVE_VALID, LIVE_PARTIAL, STALE_VALID, FAILED, UNAVAILABLE)

# Sync health vocabulary.
HEALTHY = "HEALTHY"
DEGRADED = "DEGRADED"
SYNC_FAILED = "FAILED"
SYNC_STALE = "STALE"

DEFAULT_ACCOUNT_ID = "biz_UxlhGUdO9TpGb0"
WHOP_API_BASE = os.getenv("WHOP_API_URL", "https://api.whop.com/api/v2")
STALE_AFTER_HOURS = 26          # daily schedule + slack
HTTP_TIMEOUT_SECONDS = 30


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def _parse_ts(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def get_account_id() -> str:
    acct = os.getenv("WHOP_ACCOUNT_ID", "")
    if acct:
        return acct
    for name in (".env", ".env.local"):
        f = REPO_ROOT / name
        try:
            if not f.exists():
                continue
            for line in f.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if s.startswith("WHOP_ACCOUNT_ID=") and not s.startswith("#"):
                    return s.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            continue
    return ""


def get_api_key() -> str:
    """Resolve WHOP_API_KEY from env or repo .env files. Never logged."""
    key = os.getenv("WHOP_API_KEY", "")
    if key:
        return key
    for name in (".env", ".env.local"):
        f = REPO_ROOT / name
        try:
            if not f.exists():
                continue
            for line in f.read_text(encoding="utf-8").splitlines():
                s = line.strip()
                if s.startswith("WHOP_API_KEY=") and not s.startswith("#"):
                    return s.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            continue
    return ""


def has_rest() -> bool:
    return bool(get_api_key())


# ─────────────────────────────────────────────────────────────────────────────
# Transport (injection point for tests — no monkeypatching of requests needed)
# ─────────────────────────────────────────────────────────────────────────────

def http_get_json(url: str, headers: dict, params: dict, timeout: int):
    """Perform one GET. Returns (ok, status_code, payload_or_none, error, latency_ms).

    error is a sanitized string ('' on success). Never includes secrets.
    Raises nothing: network errors are converted into ok=False results so a
    transient SSL/socket problem can never crash a sync mid-write.
    """
    started = time.monotonic()
    try:
        import requests
    except ImportError as exc:                       # pragma: no cover
        return False, 0, None, f"requests unavailable: {exc}", 0
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=timeout)
        latency_ms = int((time.monotonic() - started) * 1000)
        if resp.status_code >= 400:
            return False, resp.status_code, None, _sanitize_error(resp.text[:300]), latency_ms
        try:
            payload = resp.json() if resp.text else {}
        except ValueError:
            payload = {}
        return True, resp.status_code, payload, "", latency_ms
    except Exception as exc:                          # SSL, DNS, timeout...
        latency_ms = int((time.monotonic() - started) * 1000)
        return False, 0, None, f"{type(exc).__name__}: {exc}"[:300], latency_ms


def _sanitize_error(text: str) -> str:
    """Strip anything secret-looking before it reaches disk."""
    key = get_api_key()
    if key and key in text:
        text = text.replace(key, "***REDACTED***")
    return text.replace("\n", " ")[:300]


def _log_call(account_id, endpoint, ok, status, latency_ms, records, error=""):
    """Append one observability line. Never logs secrets."""
    entry = {
        "timestamp": _iso(utcnow()),
        "account_id": account_id,
        "endpoint": endpoint,
        "http_status": status,
        "latency_ms": latency_ms,
        "records_returned": records,
        "success": bool(ok),
        "error": error or None,
    }
    try:
        with open(SYNC_HEALTH_LOG, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=str) + "\n")
    except OSError:
        pass
    return entry


# ─────────────────────────────────────────────────────────────────────────────
# Endpoint fetchers
# ─────────────────────────────────────────────────────────────────────────────

def fetch_products(account_id, transport=None):
    """GET /products?company_id=... -> (result_dict, diag_dict)."""
    transport = transport or http_get_json
    url = f"{WHOP_API_BASE}/products"
    ok, status, payload, error, latency_ms = transport(
        url, {"Authorization": f"Bearer {get_api_key()}"},
        {"company_id": account_id}, HTTP_TIMEOUT_SECONDS)
    rows = []
    records = 0
    if ok and isinstance(payload, dict):
        rows = payload.get("data") or []
        records = len(rows)
    diag = {"endpoint": "/products", "http_status": status, "records_returned": records,
            "latency_ms": latency_ms, "error": error}
    return (rows if ok else None), diag


def fetch_plans(account_id, transport=None):
    """GET /plans?company_id=... -> (list_of_plans_or_None, diag)."""
    transport = transport or http_get_json
    url = f"{WHOP_API_BASE}/plans"
    ok, status, payload, error, latency_ms = transport(
        url, {"Authorization": f"Bearer {get_api_key()}"},
        {"company_id": account_id}, HTTP_TIMEOUT_SECONDS)
    rows = []
    records = 0
    if ok and isinstance(payload, dict):
        rows = payload.get("data") or []
        records = len(rows)
    diag = {"endpoint": "/plans", "http_status": status, "records_returned": records,
            "latency_ms": latency_ms, "error": error}
    return (rows if ok else None), diag


def fetch_memberships(account_id, transport=None):
    """GET /memberships?company_id=... (FIXED scoping param).

    Returns (count_or_None, diag). count is an int ONLY when the endpoint
    answered successfully; None means UNVERIFIED.
    """
    transport = transport or http_get_json
    url = f"{WHOP_API_BASE}/memberships"
    ok, status, payload, error, latency_ms = transport(
        url, {"Authorization": f"Bearer {get_api_key()}"},
        {"company_id": account_id}, HTTP_TIMEOUT_SECONDS)
    count = None
    if ok and isinstance(payload, dict):
        total = payload.get("total_count")
        data = payload.get("data")
        if isinstance(total, int):
            count = total
        elif isinstance(data, list):
            count = len(data)
    diag = {"endpoint": "/memberships", "http_status": status,
            "records_returned": count if count is not None else 0,
            "latency_ms": latency_ms, "error": error}
    return count, diag


def _slim_product(p):
    """Project a raw API product onto stable, honest fields."""
    prod = {
        "id": p.get("id"),
        "title": p.get("title"),
        "headline": p.get("headline"),
        "visibility": p.get("visibility"),
    }
    # v1 exposes member_count; v2 does not -> omit rather than report None.
    if p.get("member_count") is not None:
        prod["member_count"] = p.get("member_count")
    return prod


def _slim_plan(pl):
    price = pl.get("initial_price")
    try:
        price = round(float(price), 2) if price is not None else None
    except (TypeError, ValueError):
        price = None
    renewal = pl.get("renewal_price")
    try:
        renewal = round(float(renewal), 2) if renewal not in (None, "") else None
    except (TypeError, ValueError):
        renewal = None
    return {
        "plan_id": pl.get("id"),
        "product_id": pl.get("product"),
        "plan_type": pl.get("plan_type"),
        "initial_price_usd": price,
        "renewal_price_usd": renewal,
        "currency": (pl.get("base_currency") or "").upper() or None,
        "billing_period_days": pl.get("billing_period"),
        "checkout_url": pl.get("direct_link"),
        "visibility": pl.get("visibility"),
        "release_method": pl.get("release_method"),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Snapshot persistence with carry-forward protection
# ─────────────────────────────────────────────────────────────────────────────

def load_previous_snapshot(path=None) -> dict:
    p = Path(path or SNAPSHOT_FILE)
    if not p.exists():
        return {}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def classify_staleness(snapshot: dict, now=None, max_age_hours=STALE_AFTER_HOURS) -> str:
    """Classify a stored snapshot's freshness. Returns SNAPSHOT_STATES value."""
    if not snapshot:
        return UNAVAILABLE
    status = snapshot.get("snapshot_status")
    last_ok = _parse_ts(snapshot.get("last_successful_sync")) \
        or _parse_ts(snapshot.get("timestamp"))
    now = now or utcnow()
    if last_ok is None:
        return UNAVAILABLE
    age_h = (now - last_ok).total_seconds() / 3600.0
    if age_h > max_age_hours and status in (LIVE_VALID, LIVE_PARTIAL, STALE_VALID):
        return STALE_VALID
    if status in SNAPSHOT_STATES:
        return status
    # Legacy snapshots (pre-schema-2) that contain real products are still valid data.
    if snapshot.get("products"):
        return STALE_VALID if age_h > max_age_hours else LIVE_PARTIAL
    return UNAVAILABLE


def build_snapshot(account_id, transport=None, now=None) -> dict:
    """Call all endpoints, apply carry-forward, return the merged snapshot.

    Guarantees:
      - a failed endpoint NEVER blanks a previously-verified field;
      - membership/revenue honesty semantics (UNVERIFIED / UNAVAILABLE);
      - every call is observability-logged.
    """
    now = now or utcnow()
    prev = load_previous_snapshot()

    products_raw, prod_diag = fetch_products(account_id, transport)
    plans_raw, plan_diag = fetch_plans(account_id, transport)
    mem_count, mem_diag = fetch_memberships(account_id, transport)

    _log_call(account_id, prod_diag["endpoint"], products_raw is not None,
              prod_diag["http_status"], prod_diag.get("latency_ms"),
              prod_diag["records_returned"], prod_diag["error"])
    _log_call(account_id, plan_diag["endpoint"], plans_raw is not None,
              plan_diag["http_status"], plan_diag.get("latency_ms"),
              plan_diag["records_returned"], plan_diag["error"])
    _log_call(account_id, mem_diag["endpoint"], mem_count is not None,
              mem_diag["http_status"], mem_diag.get("latency_ms"),
              mem_diag["records_returned"] or 0, mem_diag["error"])

    snapshot = {
        "schema": 2,
        "account_id": account_id,
        "mode": "rest",
        "source": "whop_api_v2",
        "last_attempt": _iso(now),
        "last_successful_sync": prev.get("last_successful_sync"),
        "failure_reason": None,
        "products": [],
        "plans": [],
        "errors": [],
        "net_revenue_7d": None,          # never fabricated; stays UNAVAILABLE
        "revenue_data_status": "UNAVAILABLE",
        "memberships_active": None,
        "memberships_data_status": "UNVERIFIED",
        "memberships_reason": None,
        "members": None,
        "members_status": "UNVERIFIED",
        "_carry_forward_applied": [],
    }

    oks = []

    # -- products --------------------------------------------------------
    if products_raw is not None:
        oks.append(True)
        snapshot["products"] = [_slim_product(p) for p in products_raw]
        snapshot["last_successful_sync"] = _iso(now)
        if plans_raw is not None:
            slim = [_slim_plan(p) for p in plans_raw]
            by_product = {}
            for pl in slim:
                by_product.setdefault(pl["product_id"], []).append(pl)
            for prod in snapshot["products"]:
                prod["plans"] = by_product.get(prod["id"], [])
        else:
            snapshot["errors"].append(f"/plans: {plan_diag['error']}")
    else:
        oks.append(False)
        snapshot["errors"].append(f"/products: {prod_diag['error']}")
        if prev.get("products"):
            snapshot["products"] = prev["products"]
            snapshot["_carry_forward_applied"].append("products")

    # -- plans (secondary evidence; only trusted with a successful call) --
    if plans_raw is not None:
        snapshot["plans"] = [_slim_plan(p) for p in plans_raw]
        if products_raw is None:
            pass  # already carried forward with products
    else:
        oks.append(False)
        snapshot["errors"].append(f"/plans: {plan_diag['error']}")
        if prev.get("plans"):
            snapshot["plans"] = prev["plans"]
            snapshot["_carry_forward_applied"].append("plans")

    # -- memberships -------------------------------------------------------
    prev_mem = prev.get("memberships_active")
    prev_mem_verified = prev.get("memberships_data_status") == "VERIFIED"
    if mem_count is not None:
        oks.append(True)
        snapshot["memberships_active"] = int(mem_count)
        snapshot["memberships_data_status"] = "VERIFIED"
        snapshot["memberships_reason"] = None
        snapshot["members"] = int(mem_count)
        snapshot["members_status"] = "VERIFIED"
        if prev.get("last_successful_sync") is None or snapshot["last_successful_sync"] is None:
            pass
    else:
        oks.append(False)
        snapshot["memberships_reason"] = (
            f"MEMBERSHIPS_ENDPOINT_{mem_diag['http_status'] or 'NETWORK'}_ERROR: "
            f"{mem_diag['error']}")
        if prev_mem is not None and prev_mem_verified:
            # Carry forward a previously VERIFIED count, clearly labelled stale.
            snapshot["memberships_active"] = prev_mem
            snapshot["members"] = prev_mem
            snapshot["memberships_data_status"] = "STALE"
            snapshot["members_status"] = "STALE"
            snapshot["memberships_reason"] += " (carried forward from last verified sync)"
        elif isinstance(prev_mem, int) and not prev_mem_verified:
            snapshot["memberships_active"] = None       # drop unverified guesses
        # else: stays None -> reported as UNVERIFIED

    # net revenue: Whop REST exposes no 7d-net endpoint to this key. It stays
    # UNAVAILABLE until purchase events exist in the canonical store.
    snapshot["net_revenue_7d"] = None
    snapshot["revenue_data_status"] = "UNAVAILABLE"

    # -- overall state ------------------------------------------------------
    if all(oks):
        snapshot["snapshot_status"] = LIVE_VALID
    elif any(oks):
        snapshot["snapshot_status"] = LIVE_PARTIAL
    else:
        snapshot["snapshot_status"] = FAILED
        snapshot["failure_reason"] = "; ".join(snapshot["errors"])[:500]
        if prev.get("products"):
            # Good data preserved; mark the file state honestly.
            snapshot["snapshot_status"] = STALE_VALID if prev_mem_verified else FAILED
    if snapshot["_carry_forward_applied"] and snapshot["snapshot_status"] == LIVE_VALID:
        snapshot["snapshot_status"] = LIVE_PARTIAL
    return snapshot


def persist_snapshot(snapshot: dict, path=None) -> Path:
    """Atomic-ish write. A crash here must not corrupt the previous file."""
    p = Path(path or SNAPSHOT_FILE)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot, indent=2, default=str), encoding="utf-8")
    tmp.replace(p)
    return p


def sync_live(account_id=None, transport=None, now=None) -> dict:
    """Full sync cycle: fetch -> protect -> persist -> return snapshot."""
    account_id = account_id or get_account_id() or DEFAULT_ACCOUNT_ID
    snap = build_snapshot(account_id, transport=transport, now=now)
    persist_snapshot(snap)
    return snap


# ─────────────────────────────────────────────────────────────────────────────
# Honest reporting helpers (Phase 3 semantics)
# ─────────────────────────────────────────────────────────────────────────────

def members_report(snapshot=None) -> dict:
    """Never reports a bare 0 for an unverifiable state."""
    snap = snapshot if snapshot is not None else load_previous_snapshot()
    status = snap.get("memberships_data_status") or "UNVERIFIED"
    value = snap.get("memberships_active")
    reason = snap.get("memberships_reason")
    if status == "VERIFIED" and isinstance(value, int):
        return {"value": value, "status": "VERIFIED", "reason": None}
    return {"value": "UNVERIFIED", "status": status, "reason":
            reason or "MEMBERSHIP_DATA_NOT_VERIFIED"}


def revenue_report(snapshot=None) -> dict:
    """Revenue is UNAVAILABLE unless real purchase evidence exists."""
    snap = snapshot if snapshot is not None else load_previous_snapshot()
    if snap.get("net_revenue_7d") is None:
        return {"value": "UNAVAILABLE", "status": "UNAVAILABLE",
                "reason": "NO_REVENUE_EVIDENCE"}
    return {"value": snap.get("net_revenue_7d"), "status": "VERIFIED", "reason": None}


# ─────────────────────────────────────────────────────────────────────────────
# Sync health (Phase 15)
# ─────────────────────────────────────────────────────────────────────────────

def read_sync_log(limit=200) -> list:
    if not SYNC_HEALTH_LOG.exists():
        return []
    try:
        lines = SYNC_HEALTH_LOG.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def compute_sync_health(now=None, max_age_hours=STALE_AFTER_HOURS) -> dict:
    """HEALTHY | DEGRADED | FAILED | STALE derived from the observability log."""
    entries = read_sync_log()
    now = now or utcnow()
    if not entries:
        return {"health": SYNC_STALE if load_previous_snapshot() else UNAVAILABLE,
                "reason": "no sync attempts recorded",
                "last_attempt": None, "recent_calls": 0}
    recent = [e for e in entries
              if (now - (_parse_ts(e.get("timestamp")) or now)).total_seconds() < 3600]
    pool = recent[-10:] if recent else entries[-3:]
    fails = [e for e in pool if not e.get("success")]
    last_ts = max((_parse_ts(e.get("timestamp")) for e in entries if e.get("timestamp")),
                  default=None)
    snap = load_previous_snapshot()
    last_ok = _parse_ts(snap.get("last_successful_sync"))
    stale = (not last_ok) or ((now - last_ok).total_seconds() / 3600.0 > max_age_hours)
    if len(fails) == len(pool):
        health = SYNC_STALE if (last_ok and not stale) else SYNC_FAILED
    elif fails:
        health = DEGRADED
    else:
        health = HEALTHY if not stale else SYNC_STALE
    return {"health": health,
            "reason": (f"{len(fails)}/{len(pool)} recent calls failed"
                       if fails else "all recent calls succeeded"),
            "last_attempt": last_ts.isoformat() if last_ts else None,
            "last_successful_sync": last_ok.isoformat() if last_ok else None,
            "recent_calls": len(pool)}
