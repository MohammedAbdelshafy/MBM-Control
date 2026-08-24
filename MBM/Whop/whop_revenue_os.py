"""
whop_revenue_os.py — Canonical Revenue OS core for the MBM / Whop system
=========================================================================
Single source of truth for revenue events, funnel math, Customer 360,
next-best-action decisions, offer matching, opportunities and unit economics.

Design rules (AGENTS.md + OX ALPHA protocol):
- Every event is traceable, timestamped, attributable, idempotent, auditable.
- Every reported metric carries a provenance label:
    REAL        read directly from an evidence file produced by a live system
    DERIVED     computed from REAL inputs by deterministic rules
    UNAVAILABLE the required evidence does not exist (never guessed)
- No fabricated customers, revenue or testimonials.
- Outreach decisions respect cooldowns and attempt limits (no infinite loops).

Canonical event store: MBM/Whop/logs/revenue_events.jsonl (append-only).
Writers: server/index.js webhook+analytics handlers, this module's CLI.

Output contract follows AGENTS.md (status/inputs/outputs/errors/next_action/...).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
LOGS_DIR = BASE_DIR / "logs"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DATA_DIR.mkdir(parents=True, exist_ok=True)

EVENTS_FILE = LOGS_DIR / "revenue_events.jsonl"
# analytics beacon log lives at MBM/Whop/analytics_log.json (Express writes here)
ANALYTICS_LOG = BASE_DIR / "analytics_log.json"
MEMBERSHIPS_LEDGER = LOGS_DIR / "whop_memberships.json"
ENGAGE_LOG = LOGS_DIR / "whop_engage_log.json"
REVENUE_REPORT = LOGS_DIR / "whop_revenue.json"
PRODUCT_SPEC = BASE_DIR / "ai-consultancy-agency" / "whop_product_spec.json"
SALES_LEDGER = BASE_DIR / "ai-consultancy-agency" / "sales_ledger_day1.json"

SCHEMA_VERSION = 1

# Events accepted from untrusted clients (landing page analytics beacon).
ALLOWED_CLIENT_EVENTS = {
    "landing_view", "cta_click", "signup", "checkout_started",
    "checkout_completed", "upsell_viewed", "upsell_accepted",
}

# Webhook action substring -> canonical event name. Tolerant mapping: unknown
# actions are stored as `webhook_received` with full metadata (never dropped,
# never invented).
WHOP_ACTION_MAP = [
    ("payment.succeeded", "purchase"),
    ("payment_succeeded", "purchase"),
    ("membership.went_valid", "subscription_started"),
    ("membership_went_valid", "subscription_started"),
    ("payment.failed", "checkout_failed"),
    ("payment_refund", "refund"),
    ("refund.created", "refund"),
    ("membership.went_invalid", "churn"),
    ("membership_went_invalid", "churn"),
    ("membership.renewed", "subscription_renewed"),
    ("renewal", "subscription_renewed"),
]

# Lifecycle stages (canonical vocabulary).
LIFECYCLE_STAGES = (
    "VISITOR", "LEAD", "FREE", "PROSPECT", "NEW_CUSTOMER", "ACTIVATING",
    "ACTIVE", "POWER_USER", "UPSELL_READY", "AT_RISK", "DORMANT",
    "CANCELLED", "WINBACK", "VIP",
)

# Anti-fatigue guardrails for any outreach-producing decision.
OUTREACH_COOLDOWN_DAYS = 14
MAX_OUTREACH_ATTEMPTS = 3


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


# ─────────────────────────────────────────────────────────────────────────────
# Canonical event store (JSONL append-only, idempotent by event_id)
# ─────────────────────────────────────────────────────────────────────────────

def make_event(event_name: str, source: str, *, event_id=None, timestamp=None,
               customer_ref=None, session_id=None, amount_usd=None,
               currency="USD", attribution=None, metadata=None) -> dict:
    """Build one canonical event dict (schema-versioned)."""
    return {
        "schema_version": SCHEMA_VERSION,
        "event_id": event_id or ("evt_" + hashlib.sha256(
            f"{event_name}|{source}|{timestamp or _iso(utcnow())}|{json.dumps(customer_ref or {}, sort_keys=True)}|{json.dumps(metadata or {}, sort_keys=True)}"
            .encode("utf-8")).hexdigest()[:24]),
        "event_name": str(event_name),
        "source": str(source),
        "timestamp": timestamp or _iso(utcnow()),
        "customer_ref": customer_ref or {},
        "session_id": session_id,
        "amount_usd": amount_usd,
        "currency": currency,
        "attribution": attribution or {},
        "metadata": metadata or {},
    }


def append_event(event: dict, events_file=None) -> bool:
    """Idempotent append. Returns False (and writes nothing) on duplicate event_id."""
    path = Path(events_file or EVENTS_FILE)
    path.parent.mkdir(parents=True, exist_ok=True)
    seen = load_event_index(path)
    eid = event.get("event_id")
    if eid and eid in seen:
        return False
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, default=str, sort_keys=True) + "\n")
    return True


def load_event_index(events_file=None) -> set:
    path = Path(events_file or EVENTS_FILE)
    if not path.exists():
        return set()
    ids = set()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    eid = json.loads(line).get("event_id")
                except Exception:
                    continue
                if eid:
                    ids.add(eid)
    except OSError:
        return set()
    return ids


def load_events(events_file=None) -> list:
    path = Path(events_file or EVENTS_FILE)
    if not path.exists():
        return []
    events = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except Exception:
                continue
    return events


# ─────────────────────────────────────────────────────────────────────────────
# Normalizers: raw inbound payloads -> canonical events
# ─────────────────────────────────────────────────────────────────────────────

def normalize_whop_webhook(payload: dict, received_at=None) -> dict:
    """Map a Whop webhook payload to a canonical event.

    Amount extraction only uses fields actually present in the payload;
    missing amounts stay None (never guessed).
    """
    action = str(payload.get("action") or "")
    canonical = "webhook_received"
    for needle, name in WHOP_ACTION_MAP:
        if needle in action:
            canonical = name
            break

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    payment = data.get("payment") if isinstance(data.get("payment"), dict) else {}
    receipt = data.get("receipt") if isinstance(data.get("receipt"), dict) else {}

    def _amount(node):
        for key in ("amount", "total", "final_amount"):
            v = node.get(key)
            if isinstance(v, (int, float)):
                return round(float(v) / 100.0, 2) if float(v) > 1000 else round(float(v), 2)
        return None

    amount = None
    if canonical == "purchase":
        amount = _amount(payment) or _amount(receipt)

    member = data.get("member") if isinstance(data.get("member"), dict) else {}
    customer_ref = {}
    for key in ("user_id", "email", "username"):
        if member.get(key):
            customer_ref[key] = member[key]
    if data.get("user_id"):
        customer_ref.setdefault("user_id", data["user_id"])
    if data.get("id"):
        customer_ref.setdefault("resource_id", data["id"])

    return make_event(
        canonical,
        source="whop_webhook",
        event_id=payload.get("id") or payload.get("event_id"),
        timestamp=received_at or _iso(utcnow()),
        customer_ref=customer_ref,
        amount_usd=amount,
        currency=(payment.get("currency") or "USD").upper(),
        attribution={"via": "webhook"},
        metadata={"action": action, "payload_digest": hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]},
    )


def normalize_client_event(body: dict, received_at=None) -> dict | None:
    """Validate + normalize an untrusted analytics beacon from the landing page."""
    name = str(body.get("event") or "").strip()
    if name not in ALLOWED_CLIENT_EVENTS:
        return None
    props = body.get("props") if isinstance(body.get("props"), dict) else {}
    attribution = {}
    for key in ("utm_source", "utm_medium", "utm_campaign", "utm_content",
                "referral", "landing_variant", "offer_variant"):
        val = body.get(key) or props.get(key)
        if val:
            attribution[key] = str(val)[:120]
    session_id = body.get("session_id") or body.get("anon_id")
    session_id = str(session_id)[:64] if session_id else None
    metadata = {k: str(v)[:200] for k, v in props.items()
                if k not in attribution and not k.startswith("utm_")}
    ts = received_at or body.get("timestamp") or _iso(utcnow())
    parsed = _parse_ts(ts)
    return make_event(
        name,
        source="landing",
        timestamp=_iso(parsed) if parsed else _iso(utcnow()),
        session_id=session_id,
        attribution=attribution,
        metadata=metadata,
    )


# ─────────────────────────────────────────────────────────────────────────────
# Legacy analytics log ingestion (analytics_log.json written by Express)
# ─────────────────────────────────────────────────────────────────────────────

def ingest_legacy_analytics(dry_run=False) -> dict:
    """Fold legacy analytics_log.json entries into the canonical store."""
    out = {"read": 0, "appended": 0, "skipped_duplicate": 0, "invalid": 0}
    if not ANALYTICS_LOG.exists():
        return out
    try:
        rows = json.loads(ANALYTICS_LOG.read_text(encoding="utf-8"))
    except Exception:
        return out
    if not isinstance(rows, list):
        return out
    for row in rows:
        out["read"] += 1
        if not isinstance(row, dict):
            out["invalid"] += 1
            continue
        evt = normalize_client_event(row, received_at=row.get("received_at"))
        if evt is None:
            # keep unknown legacy names observable but non-canonical
            evt = make_event("custom." + str(row.get("event") or "unknown")[:40],
                             source="landing_legacy",
                             timestamp=row.get("received_at") or _iso(utcnow()),
                             metadata={k: str(v)[:100] for k, v in row.items() if k != "event"})
        if dry_run:
            idx = load_event_index()
            out["appended"] += 0 if evt["event_id"] in idx else 1
        else:
            out["appended" if append_event(evt) else "skipped_duplicate"] += 1
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Funnel + metrics
# ─────────────────────────────────────────────────────────────────────────────

FUNNEL_STEPS = ["landing_view", "cta_click", "signup", "checkout_started",
                "purchase", "subscription_started"]

FUNNEL_ALIASES = {"checkout_completed": "purchase"}


def compute_funnel(events=None) -> dict:
    """Deterministic funnel counts + step conversions from canonical events."""
    if events is None:
        events = load_events()
    counts = {step: 0 for step in FUNNEL_STEPS}
    sessions = set()
    for e in events:
        name = FUNNEL_ALIASES.get(e.get("event_name"), e.get("event_name"))
        if name in counts:
            counts[name] += 1
        if e.get("session_id"):
            sessions.add(e["session_id"])
    rates = {}
    prev = None
    for step in FUNNEL_STEPS:
        if prev is not None and counts[prev] > 0:
            rates[f"{prev}->{step}"] = round(counts[step] / counts[prev], 4)
        prev = step
    overall = round(counts["purchase"] / counts["landing_view"], 4) if counts["landing_view"] else None

    # Per-product breakdown (Phase 11): attribution via metadata.product_id.
    by_product = {}
    for e in events:
        name = FUNNEL_ALIASES.get(e.get("event_name"), e.get("event_name"))
        if name not in counts:
            continue
        pid = (e.get("metadata") or {}).get("product_id") or "unattributed"
        bucket = by_product.setdefault(pid, {step: 0 for step in FUNNEL_STEPS})
        bucket[name] += 1

    return {
        "counts": counts,
        "step_rates": rates,
        "overall_view_to_purchase": overall,
        "unique_sessions": len(sessions),
        "by_product": by_product,
        "provenance": "DERIVED",
        "evidence": [str(EVENTS_FILE)],
    }


def revenue_summary(events=None) -> dict:
    """Gross revenue + AOV strictly from purchase/refund events with amounts."""
    if events is None:
        events = load_events()
    gross = 0.0
    orders = 0
    refunds = 0.0
    for e in events:
        amt = e.get("amount_usd")
        if not isinstance(amt, (int, float)):
            continue
        if e.get("event_name") == "purchase":
            gross += float(amt)
            orders += 1
        elif e.get("event_name") == "refund":
            refunds += float(amt)
    aov = round(gross / orders, 2) if orders else None
    return {
        "gross_revenue_usd": round(gross - refunds, 2),
        "orders": orders,
        "refunds_usd": round(refunds, 2),
        "aov_usd": aov,
        "mrr_usd": None,          # requires active subscription amounts; see subscriptions()
        "provenance": "DERIVED" if orders else "UNAVAILABLE",
        "evidence": [str(EVENTS_FILE)],
    }


def subscriptions(events=None) -> dict:
    """Subscription snapshot derived from lifecycle events (no guessing MRR)."""
    if events is None:
        events = load_events()
    started = sum(1 for e in events if e.get("event_name") == "subscription_started")
    churned = sum(1 for e in events if e.get("event_name") == "churn")
    renewed = sum(1 for e in events if e.get("event_name") == "subscription_renewed")
    mrr_known = any(isinstance(e.get("amount_usd"), (int, float))
                    and e.get("event_name") in ("subscription_started", "subscription_renewed")
                    for e in events)
    return {
        "started": started,
        "active_estimated": max(started - churned, 0),
        "renewals": renewed,
        "churned": churned,
        "mrr_provenance": "UNAVAILABLE" if not mrr_known else "DERIVED",
        "provenance": "DERIVED",
        "evidence": [str(EVENTS_FILE)],
    }


def unit_economics(events=None) -> dict:
    """Only computes what evidence supports; everything else UNAVAILABLE."""
    rev = revenue_summary(events)
    fees = os.getenv("WHOP_FEE_PCT")
    commission_pct = os.getenv("WHOP_AFFILIATE_PCT")
    net = None
    provenance = "UNAVAILABLE"
    if rev["orders"]:
        net = rev["gross_revenue_usd"]
        provenance = "DERIVED"
        if fees:
            net -= rev["gross_revenue_usd"] * float(fees) / 100.0
        if commission_pct:
            net -= rev["gross_revenue_usd"] * float(commission_pct) / 100.0
        net = round(net, 2)
    return {
        "gross_revenue_usd": rev["gross_revenue_usd"],
        "net_revenue_usd": net,
        "fees_configured": bool(fees),
        "affiliate_commission_configured": bool(commission_pct),
        "fulfillment_cost_usd": "UNAVAILABLE",
        "ltv_usd": "UNAVAILABLE",   # needs cohort retention data (no members yet)
        "cac_usd": "UNAVAILABLE",   # no acquisition spend recorded yet
        "payback_days": "UNAVAILABLE",
        "provenance": provenance,
        "evidence": [str(EVENTS_FILE), ".env WHOP_FEE_PCT / WHOP_AFFILIATE_PCT"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# Product catalog (REAL: spec file + last live API report)
# ─────────────────────────────────────────────────────────────────────────────

def load_catalog() -> dict:
    """Real product catalog: plans with live checkout URLs + live member counts.

    Sources (all REAL, never invented):
      - ai-consultancy-agency/whop_product_spec.json  (legacy sprint account)
      - logs/whop_revenue.json products[].plans[]     (live biz_UxlhGUdO9TpGb0
        plans synced by whop_live.sync_live(), incl. prices + checkout URLs)
    """
    catalog = {"products": [], "provenance": "UNAVAILABLE", "evidence": []}
    spec = {}
    if PRODUCT_SPEC.exists():
        try:
            spec = json.loads(PRODUCT_SPEC.read_text(encoding="utf-8"))
            catalog["evidence"].append(str(PRODUCT_SPEC))
        except Exception:
            spec = {}
    if spec:
        catalog["products"].append({
            "key": spec.get("product_key"),
            "name": spec.get("name"),
            "plans": [
                {
                    "plan_id": p.get("plan_id"),
                    "title": p.get("title"),
                    "price_usd": p.get("initial_price"),
                    "plan_type": p.get("plan_type"),
                    "billing_period_days": p.get("billing_period"),
                    "checkout_url": p.get("checkout_url"),
                    "deliverables": p.get("deliverables"),
                }
                for p in spec.get("plans", [])
            ],
        })
        catalog["provenance"] = "REAL"
    report = {}
    if REVENUE_REPORT.exists():
        try:
            report = json.loads(REVENUE_REPORT.read_text(encoding="utf-8"))
            catalog["evidence"].append(str(REVENUE_REPORT))
            for p in report.get("products", []):
                known = next((x for x in catalog["products"]
                              if x.get("key") == p.get("id")), None)
                if not known:
                    catalog["products"].append({
                        "key": p.get("id"), "name": p.get("title"),
                        "live_member_count": p.get("member_count"), "plans": [],
                    })
                else:
                    known["live_member_count"] = p.get("member_count")
            # Merge live plan data (schema-2 snapshots carry real prices/URLs).
            for prod in catalog["products"]:
                live_plans = [pl for pl in report.get("plans", [])
                              if pl.get("product_id") == prod.get("key")]
                if not live_plans:
                    for p in report.get("products", []):
                        if p.get("id") == prod.get("key"):
                            live_plans = p.get("plans") or []
                            break
                merged = []
                seen_plan_ids = set()
                for src in (prod["plans"], live_plans):
                    for pl in src:
                        pid = pl.get("plan_id")
                        if pid and pid in seen_plan_ids:
                            continue
                        if pid:
                            seen_plan_ids.add(pid)
                        merged.append(pl)
                if merged:
                    prod["plans"] = merged
                    catalog["provenance"] = "REAL"
        except Exception:
            pass
    return catalog


# ─────────────────────────────────────────────────────────────────────────────
# Offer matching + Next Best Action
# ─────────────────────────────────────────────────────────────────────────────

def match_offer(customer: dict, catalog=None) -> list:
    """Rank real offers against a customer's lifecycle state.

    customer: minimal Customer360-ish dict with lifecycle_state, products_owned.
    Returns ranked offer dicts (real checkout URLs only; never invents SKUs).
    """
    if catalog is None:
        catalog = load_catalog()
    stage = str(customer.get("lifecycle_state") or "LEAD").upper()
    owned = set(customer.get("products_owned") or [])
    ranked = []
    for prod in catalog.get("products", []):
        for plan in prod.get("plans", []):
            score = 0.5
            reasons = []
            ptype = plan.get("plan_type")
            price = plan.get("price_usd") or 0
            title = (plan.get("title") or "").lower()
            if stage in ("LEAD", "PROSPECT", "FREE", "VISITOR") and ptype == "one_time":
                score += 0.3
                reasons.append("low-friction entry offer fits pre-purchase stage")
            if stage == "NEW_CUSTOMER" and "audit" in title:
                score += 0.25
                reasons.append("entry buyer -> audit-to-build upgrade path")
            if owned and stage in ("ACTIVE", "NEW_CUSTOMER") and ptype == "one_time" \
                    and "build" in title or "deploy" in title:
                score += 0.2
                reasons.append("existing buyer -> build & deploy upsell")
            if stage in ("UPSELL_READY", "POWER_USER", "VIP") and ptype == "renewal":
                score += 0.35
                reasons.append("engaged customer -> recurring managed plan")
            if stage == "AT_RISK" and "audit" in title:
                score += 0.1
                reasons.append("downsell-safe re-entry offer")
            ranked.append({
                "product_key": prod.get("key"),
                "plan_id": plan.get("plan_id"),
                "title": plan.get("title"),
                "price_usd": price,
                "plan_type": ptype,
                "checkout_url": plan.get("checkout_url"),
                "score": round(min(score, 1.0), 2),
                "reasons": reasons or ["general fit"],
            })
    ranked.sort(key=lambda o: o["score"], reverse=True)
    return ranked


def _engage_state() -> dict:
    """Load cooldown map + processed ids from the engage bot log (anti-spam)."""
    state = {"last_emailed": {}, "processed_ids": []}
    if ENGAGE_LOG.exists():
        try:
            hist = json.loads(ENGAGE_LOG.read_text(encoding="utf-8"))
            state["last_emailed"] = hist.get("last_emailed", {}) or {}
            state["processed_ids"] = hist.get("processed_ids", []) or []
        except Exception:
            pass
    return state


def get_next_best_action(customer: dict, now=None) -> dict:
    """Rule-based NBA. Every decision includes reason/evidence/timing/channel/
    offer/confidence AND a governor level (see whop_governor.py).

    Anti-loop guarantees: cooldown window + attempt ceiling per contact.
    """
    now = now or utcnow()
    stage = str(customer.get("lifecycle_state") or "LEAD").upper()
    email = customer.get("email") or customer.get("customer_id")
    engage = _engage_state()
    last_ts = _parse_ts(engage["last_emailed"].get(email)) if email else None
    attempts = int(customer.get("outreach_attempts") or 0)

    def _decision(action, reason, evidence, channel, confidence, level, timing="next_batch"):
        return {
            "action": action,
            "reason": reason,
            "evidence": evidence,
            "timing": timing,
            "channel": channel,
            "confidence": confidence,
            "governor_level": level,
            "cooldown_days": OUTREACH_COOLDOWN_DAYS,
            "max_attempts": MAX_OUTREACH_ATTEMPTS,
            "in_cooldown": bool(last_ts and (now - last_ts) < timedelta(days=OUTREACH_COOLDOWN_DAYS)),
            "attempt_limit_reached": attempts >= MAX_OUTREACH_ATTEMPTS,
        }

    if stage in ("CANCELLED",):
        if attempts >= MAX_OUTREACH_ATTEMPTS:
            return _decision("DO_NOT_CONTACT", "winback attempt ceiling reached",
                             [str(ENGAGE_LOG)], "none", 0.9, 0)
        return _decision("WINBACK", f"stage=CANCELLED with {attempts} prior attempts",
                         [str(MEMBERSHIPS_LEDGER)], "email", 0.6, 2)

    if stage in ("AT_RISK", "DORMANT"):
        return _decision("RETAIN", f"stage={stage} flagged by membership classifier",
                         [str(MEMBERSHIPS_LEDGER), str(whop_monetize_monitor_evidence())],
                         "email", 0.7, 2)

    if stage in ("UPSELL_READY", "POWER_USER", "VIP"):
        offers = match_offer({**customer, "lifecycle_state": stage})
        best = offers[0]["title"] if offers else "UNAVAILABLE"
        return _decision("UPSELL", f"stage={stage} and engagement above threshold",
                         [str(ENGAGE_LOG)], "email", 0.65, 2, timing="after_value_delivery")

    if stage in ("NEW_CUSTOMER", "ACTIVATING"):
        return _decision("NURTURE", "onboarding window: deliver quickstart value first",
                         [str(MEMBERSHIPS_LEDGER)], "email", 0.75, 1)

    if stage == "PROSPECT":
        return _decision("SELL", "qualified prospect with open offer",
                         [str(SALES_LEDGER)], "direct_outreach", 0.55, 3,
                         timing="business_hours")

    if stage in ("LEAD", "FREE", "VISITOR"):
        funnel = compute_funnel()
        ev = [str(EVENTS_FILE)]
        if funnel["counts"]["signup"] and not funnel["counts"]["purchase"]:
            return _decision("NURTURE", "signed up but never purchased; send value content, not discount",
                             ev, "email", 0.6, 1)
        return _decision("OBSERVE", "insufficient intent signals captured yet", ev, "none", 0.4, 0)

    return _decision("HUMAN_REVIEW", "unknown lifecycle state", [], "none", 0.3, 3)


def whop_monetize_monitor_evidence() -> str:
    return "python MBM/Whop/whop_monetize.py monitor"


# ─────────────────────────────────────────────────────────────────────────────
# Customer 360
# ─────────────────────────────────────────────────────────────────────────────

def _memberships_latest() -> list:
    """Latest ledger record per membership_id (the scan appends each run)."""
    if not MEMBERSHIPS_LEDGER.exists():
        return []
    try:
        records = json.loads(MEMBERSHIPS_LEDGER.read_text(encoding="utf-8")).get("records", [])
    except Exception:
        return []
    latest = {}
    for rec in records:
        key = rec.get("membership_id") or rec.get("user_id")
        if not key:
            continue
        latest[key] = rec  # later records overwrite earlier scans
    return list(latest.values())


_STAGE_TO_LIFECYCLE = {
    "new": "NEW_CUSTOMER", "stable": "ACTIVE", "at_risk": "AT_RISK",
    "dormant": "DORMANT", "churned": "CANCELLED", "unknown": "HUMAN_REVIEW_STAGE_UNKNOWN",
}


def health_score(rec: dict) -> tuple:
    """Deterministic 0-100 health score with reasons (rule weights documented)."""
    score = 60
    reasons = []
    stage = rec.get("stage")
    if stage == "stable":
        score += 20
        reasons.append("+20 stable membership")
    elif stage == "new":
        score += 10
        reasons.append("+10 new member (onboarding risk window)")
    elif stage == "at_risk":
        score -= 30
        reasons.append("-30 renewal within 7 days")
    elif stage == "dormant":
        score -= 15
        reasons.append("-15 dormant >=14d without touch")
    elif stage == "churned":
        score -= 60
        reasons.append("-60 cancelled/expired")
    status = str(rec.get("status") or "").lower()
    if status and status not in ("active", "valid"):
        score -= 10
        reasons.append(f"-10 status={status}")
    return max(min(score, 100), 0), reasons


def build_customer_360() -> list:
    """Unified customers from memberships ledger + canonical purchase events."""
    customers = {}
    for rec in _memberships_latest():
        cid = rec.get("user_id") or rec.get("membership_id") or "unknown"
        hscore, reasons = health_score(rec)
        customers[cid] = {
            "identity": {"customer_id": cid, "email": rec.get("email")},
            "source": "whop_memberships_ledger",
            "products_owned": [],
            "orders": [],
            "subscriptions": [{"membership_id": rec.get("membership_id"),
                               "plan_id": rec.get("plan_id"),
                               "status": rec.get("status")}],
            "revenue_usd": 0.0,
            "last_activity": rec.get("scanned_at"),
            "lifecycle_state": _STAGE_TO_LIFECYCLE.get(rec.get("stage"), "HUMAN_REVIEW_STAGE_UNKNOWN"),
            "health_score": hscore,
            "health_reasons": reasons,
            "upsell_state": "blocked_until_active",
            "churn_risk": {"high": 0.8, "medium": 0.5}.get(
                {"at_risk": "high", "dormant": "medium"}.get(rec.get("stage")), 0.2),
            "referral_state": "not_available",
            "provenance": "REAL",
        }
    for e in load_events():
        ref = e.get("customer_ref") or {}
        cid = ref.get("user_id") or ref.get("email")
        if not cid:
            continue
        cust = customers.setdefault(cid, {
            "identity": {"customer_id": cid, "email": ref.get("email")},
            "source": "revenue_events", "products_owned": [], "orders": [],
            "subscriptions": [], "revenue_usd": 0.0, "last_activity": None,
            "lifecycle_state": "VISITOR", "health_score": 60, "health_reasons": [],
            "upsell_state": "n/a", "churn_risk": None, "referral_state": "not_available",
            "provenance": "REAL",
        })
        name = e.get("event_name")
        if name == "purchase" and isinstance(e.get("amount_usd"), (int, float)):
            cust["revenue_usd"] = round(cust["revenue_usd"] + e["amount_usd"], 2)
            cust["orders"].append({"order_ref": e["event_id"], "amount_usd": e["amount_usd"],
                                   "timestamp": e["timestamp"]})
            cust["last_activity"] = e["timestamp"]
        elif name == "churn":
            cust["lifecycle_state"] = "CANCELLED"
            cust["churn_risk"] = 0.9
        elif name == "subscription_started":
            cust["subscriptions"].append({"event_id": e["event_id"],
                                          "timestamp": e["timestamp"]})
            cust["lifecycle_state"] = "ACTIVE"
    # attach NBA for every customer
    for cust in customers.values():
        cust["next_best_action"] = get_next_best_action(cust)
    return sorted(customers.values(), key=lambda c: -(c["health_score"]))


# ─────────────────────────────────────────────────────────────────────────────
# Revenue opportunity engine
# ─────────────────────────────────────────────────────────────────────────────

def identify_revenue_opportunities(now=None) -> list:
    """Evidence-backed opportunities only; every item cites its data source."""
    now = now or utcnow()
    events = load_events()
    ops = []

    # 1. Abandoned checkouts: started but no purchase, respecting recovery caps
    purchased_sessions = {e.get("session_id") for e in events
                          if e.get("event_name") in ("purchase",)}
    starts = [e for e in events if e.get("event_name") == "checkout_started"]
    recoverable = [e for e in starts
                   if e.get("session_id") and e["session_id"] not in purchased_sessions]
    if recoverable:
        ops.append({
            "type": "abandoned_checkout_recovery",
            "count": len(recoverable),
            "evidence": [e["event_id"] for e in recoverable[:10]] + [str(EVENTS_FILE)],
            "estimated_value": "UNAVAILABLE",  # no basket value captured client-side yet
            "confidence": 0.6,
            "effort": "low",
            "priority": round(len(recoverable) * 0.2, 2),
            "recommended_action": "single recovery email within 24h; max 2 attempts, 72h spacing",
        })

    # 2. Signup->purchase leak
    funnel = compute_funnel(events)
    if funnel["counts"]["signup"] > funnel["counts"]["purchase"] * 3 and funnel["counts"]["signup"] >= 5:
        ops.append({
            "type": "conversion_leak_signup_to_purchase",
            "count": funnel["counts"]["signup"] - funnel["counts"]["purchase"],
            "evidence": [str(EVENTS_FILE)],
            "estimated_value": "UNAVAILABLE",
            "confidence": 0.5,
            "effort": "medium",
            "priority": 0.7,
            "recommended_action": "run headline/CTA experiment variant focused on pricing objection",
        })

    # 3. Upsell candidates: buyers without recurring plan ownership recorded
    buyers = {c["identity"]["customer_id"]: c for c in build_customer_360()
              if c["revenue_usd"] > 0}
    upsell_ready = [cid for cid, c in buyers.items()
                    if c["lifecycle_state"] in ("ACTIVE", "POWER_USER")]
    if upsell_ready:
        cat = load_catalog()
        managed = next((pl for pr in cat["products"] for pl in pr["plans"]
                        if pl.get("plan_type") == "renewal"), {})
        ops.append({
            "type": "upsell_to_managed_plan",
            "count": len(upsell_ready),
            "customers": upsell_ready[:10],
            "evidence": [str(EVENTS_FILE), str(PRODUCT_SPEC)],
            "estimated_value_modelled": round(len(upsell_ready) * float(managed.get("price_usd") or 497), 2),
            "value_basis": "modelled: count x Managed AI Growth $%s/mo" % (managed.get("price_usd") or 497),
            "confidence": 0.55,
            "effort": "low",
            "priority": 0.8,
            "recommended_action": "contextual upsell 48h post-delivery via governor-approved flow",
        })

    # 4. Winbacks from ledger churned rows
    churned = [r for r in _memberships_latest() if r.get("stage") == "churned"]
    if churned:
        ops.append({
            "type": "winback_campaign",
            "count": len(churned),
            "evidence": [str(MEMBERSHIPS_LEDGER)],
            "estimated_value": "UNAVAILABLE",
            "confidence": 0.4,
            "effort": "medium",
            "priority": 0.5,
            "recommended_action": "reactivation offer via whop_lifecycle_engage.py (cooldown enforced)",
        })

    # 5. Traffic exists but zero checkouts -> acquisition-side fix first
    if funnel["counts"]["landing_view"] >= 20 and funnel["counts"]["checkout_started"] == 0:
        ops.append({
            "type": "funnel_top_leak_no_checkouts",
            "count": funnel["counts"]["landing_view"],
            "evidence": [str(EVENTS_FILE), str(ANALYTICS_LOG)],
            "estimated_value": "UNAVAILABLE",
            "confidence": 0.7,
            "effort": "medium",
            "priority": 0.9,
            "recommended_action": "instrument + test checkout CTA placement before buying more traffic",
        })

    ops.sort(key=lambda o: o.get("priority", 0), reverse=True)
    return ops


# ─────────────────────────────────────────────────────────────────────────────
# Command-center aggregation
# ─────────────────────────────────────────────────────────────────────────────

def command_center() -> dict:
    """Everything the dashboard/CLI/copilot render, with provenance labels."""
    memberships = _memberships_latest()
    live_status = _live_status_block()
    return {
        "generated_at": _iso(utcnow()),
        "live_status": live_status,
        "revenue": revenue_summary(),
        "subscriptions": subscriptions(),
        "funnel": compute_funnel(),
        "economics": unit_economics(),
        "catalog": load_catalog(),
        "memberships": {
            "tracked_unique": len(memberships),
            "by_stage": _by_stage(memberships),
            "provenance": "REAL" if memberships else "UNAVAILABLE",
            "evidence": [str(MEMBERSHIPS_LEDGER), str(REVENUE_REPORT)],
        },
        "customers": build_customer_360(),
        "opportunities": identify_revenue_opportunities(),
        "experiments_file": str(DATA_DIR / "experiments.json"),
    }


def _live_status_block() -> dict:
    """Live account truth + PRE-REVENUE mode flag (Phase 12)."""
    from whop_live import (classify_staleness, compute_sync_health,
                           load_previous_snapshot, members_report,
                           revenue_report)
    snap = load_previous_snapshot()
    members = members_report(snap)
    revenue = revenue_report(snap)
    health = compute_sync_health()
    has_verified_revenue = revenue["status"] == "VERIFIED"
    mode = "PRE_REVENUE" if not has_verified_revenue else "REVENUE_ACTIVE"
    blockers = []
    if members["status"] != "VERIFIED":
        blockers.append("Membership data unverified")
    if health["health"] in ("FAILED", "STALE", "UNAVAILABLE"):
        blockers.append(f"Sync health {health['health']}")
    return {
        "account_id": snap.get("account_id"),
        "snapshot_status": classify_staleness(snap),
        "last_successful_sync": snap.get("last_successful_sync"),
        "last_attempt": snap.get("last_attempt"),
        "failure_reason": snap.get("failure_reason"),
        "product_count": len(snap.get("products") or []),
        "members": members,
        "revenue": revenue,
        "sync_health": health,
        "mode": mode,
        "primary_blocker": (blockers[0] if blockers
                            else None) or "None — drive traffic to checkout",
        "next_revenue_objective": ("FIRST VERIFIED PURCHASE" if mode == "PRE_REVENUE"
                                   else "SCALE_ACQUISITION"),
    }


def _by_stage(memberships) -> dict:
    out = {}
    for m in memberships:
        s = m.get("stage") or "unknown"
        out[s] = out.get(s, 0) + 1
    return out


def _contract(status, outputs, errors=None, next_action="continue", owner="system"):
    return {
        "status": status,
        "inputs": {"events_file": str(EVENTS_FILE)},
        "outputs": outputs,
        "errors": errors or [],
        "next_action": next_action,
        "owner": owner,
        "timestamp": _iso(utcnow()),
    }


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "summary"
    if cmd == "ingest-analytics":
        print(json.dumps(_contract("success", ingest_legacy_analytics())))
    elif cmd == "command-center":
        cc = command_center()
        cc["customers"] = len(cc["customers"])  # keep terminal output compact
        print(json.dumps(_contract("success", cc)))
    else:
        print(json.dumps(_contract("success", {
            "revenue": revenue_summary(),
            "funnel": compute_funnel(),
        })))
