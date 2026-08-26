#!/usr/bin/env python3
"""
Revenue Scoreboard — EVENT-DERIVED ONLY (zero-simulation law)
=============================================================
Every number is computed from:
  1. MBM/LeadEngine/logs/outreach_events.jsonl   (canonical call/commercial events)
  2. MBM/Whop/logs/revenue_events.jsonl          (landing CTAs + Whop webhook normalizations)
  3. mbm-dialer/app/public/leads_database.json   (verified prospect pool counts)

Anything without an underlying event row = 0.

Usage:
  python MBM/LeadEngine/revenue_scoreboard.py            # today (UTC)
  python MBM/LeadEngine/revenue_scoreboard.py --day YYYY-MM-DD
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parent
ROOT = BASE.parent.parent
sys.path.insert(0, str(BASE))
sys.stdout.reconfigure(encoding="utf-8")

from outreach_event import load_events, funnel_counts, import_legacy_dispositions  # noqa: E402

OUTREACH_STORE = BASE / "logs" / "outreach_events.jsonl"
REVENUE_EVENTS = ROOT / "MBM" / "Whop" / "logs" / "revenue_events.jsonl"
DIALER_DB = ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"
DENTAL_QUEUE = (
    ROOT / "MBM" / "Artifacts" / "GTM" / "campaigns" /
    "CAMP-DENTAL-DFW-MCR-001" / "OX3_OUTPUT_DENTAL-GOLD-002.json"
)
SCOREBOARD_DIR = ROOT / "MBM" / "Artifacts" / "GTM" / "daily"

PAYMENT_EVENT_NAMES = {"purchase", "subscription_started", "subscription_renewed"}
CHECKOUT_CLICK_NAMES = {"checkout_started"}


def _load_json(path: Path):
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def _load_jsonl(path: Path):
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def prospect_pool() -> dict:
    db = _load_json(DIALER_DB)
    rows = []
    if isinstance(db, list):
        rows = db
    elif isinstance(db, dict):
        rows = db.get("leads") or db.get("data") or []
    npi = sum(1 for r in rows if "NPI" in str(r.get("source", "")))
    verified_phone = sum(1 for r in rows if str(r.get("phone_verified", "")).lower() == "true")
    queue = _load_json(DENTAL_QUEUE) or {}
    return {
        "dialer_rows_total": len(rows),
        "npi_registry_sourced": npi,
        "phone_verified_rows": verified_phone,
        "call_ready_dental": int(queue.get("call_ready_count") or len(queue.get("ranked_call_queue") or [])),
    }


def telephony_block() -> dict:
    """REAL bridge capability report — never claims readiness it doesn't have."""
    try:
        from free_us_phone_dialer import telephony_status
        status = telephony_status()
    except Exception:
        status = {"status": "TELEPHONY_BLOCKED", "provider": "twilio", "required_integration": "free_us_phone_dialer unavailable"}
    # Trial-account restriction observed in legacy close_dispositions.json:
    # "TRIAL account: can only call numbers in verified_caller_ids"
    if status.get("status") == "READY":
        status["known_restriction"] = (
            "Twilio account previously returned TRIAL restriction "
            "(verified_caller_ids only). Verify billing/upgrade before live dials."
        )
    return status


def build(day: str) -> dict:
    import_legacy_dispositions()
    events_all = load_events()
    events_today = [e for e in events_all if str(e.get("timestamp", "")).startswith(day)]
    funnel = funnel_counts(events_today)
    funnel_lifetime = funnel_counts(events_all)

    rev_rows = [r for r in _load_jsonl(REVENUE_EVENTS) if str(r.get("timestamp", "")).startswith(day)]
    checkout_clicks = sum(1 for r in rev_rows if r.get("event_name") in CHECKOUT_CLICK_NAMES)
    cta_clicks = sum(1 for r in rev_rows if r.get("event_name") == "cta_click")
    payments = [
        r for r in rev_rows
        if r.get("event_name") in PAYMENT_EVENT_NAMES and float(r.get("amount_usd") or 0) > 0
    ]
    revenue = round(sum(float(p.get("amount_usd") or 0) for p in payments), 2)
    refunds = sum(abs(float(r.get("amount_usd") or 0)) for r in rev_rows if r.get("event_name") == "refund")

    pool = prospect_pool()
    telephony = telephony_block()

    scoreboard = {
        "date": day,
        "status": None,
        "owner": "system",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "metric_source": "events_only (outreach_events.jsonl + revenue_events.jsonl)",
        "verified_prospects": pool["npi_registry_sourced"],
        "pool": pool,
        "call_ready": pool["call_ready_dental"],
        "email_ready": 0,
        "calls_attempted": funnel["calls_attempted"],
        "connected": funnel["connected"],
        "conversations": funnel["conversations"],
        "wrong_numbers": funnel["wrong_numbers"],
        "wrong_parties": funnel["wrong_parties"],
        "no_answers": funnel["no_answers"],
        "voicemails": funnel["voicemails"],
        "do_not_call": funnel["do_not_call"],
        "callbacks": funnel["callbacks"],
        "qualified": funnel["qualified"],
        "followups": funnel["callbacks"],
        "offers": funnel["offers_sent"],
        "appointments": funnel["appointments"],
        "checkout_clicks": checkout_clicks,
        "landing_cta_clicks": cta_clicks,
        "payments": len(payments),
        "refunds": refunds,
        "revenue": max(0.0, revenue - refunds),
        "pipeline_value": 0.0,
        "pipeline_note": "pipeline_value counts PAID money only until a real CRM pipeline stage exists",
        "telephony": telephony,
        "targets_2026_08_26": {
            "real_calls": 10, "conversations": 5, "offers": 2,
            "appointments": 1, "payment_opportunities": 1,
        },
        "inputs": {"outreach_events_today": len(events_today), "outreach_events_lifetime": len(events_all), "revenue_events_today": len(rev_rows)},
        "lifetime_funnel": funnel_lifetime,
        "outputs": {},
        "errors": [],
        "next_action": "Dial the DENTAL-GOLD sprint queue live and record dispositions.",
    }
    if (scoreboard["payments"] > 0 or scoreboard["revenue"] > 0
            or scoreboard["appointments"] > 0 or scoreboard["conversations"] > 0):
        scoreboard["status"] = "GREEN"
    else:
        scoreboard["status"] = "YELLOW"
    return scoreboard


def main() -> None:
    ap = argparse.ArgumentParser(description="Event-derived daily revenue scoreboard")
    ap.add_argument("--day", default=datetime.now(timezone.utc).date().isoformat())
    args = ap.parse_args()

    board = build(args.day)
    day_dir = SCOREBOARD_DIR / args.day
    day_dir.mkdir(parents=True, exist_ok=True)
    out_path = day_dir / "revenue_scoreboard.json"
    out_path.write_text(json.dumps(board, indent=2), encoding="utf-8")
    board["outputs"] = {"scoreboard": str(out_path)}

    print(f"REVENUE SCOREBOARD {args.day} [{board['status']}] -> {out_path}")
    for key in ("calls_attempted", "conversations", "wrong_numbers", "wrong_parties",
                "callbacks", "offers", "appointments", "checkout_clicks",
                "payments", "revenue"):
        print(f"  {key:>18}: {board[key]}")


if __name__ == "__main__":
    main()
