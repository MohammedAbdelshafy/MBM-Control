#!/usr/bin/env python3
"""Daily REAL revenue scoreboard - event-derived ONLY (zero-simulation law).

Sources:
  1. MBM/LeadEngine/logs/outreach_events.jsonl   canonical outreach events
  2. MBM/Whop/logs/revenue_events.jsonl          landing CTA / Whop webhook events
  3. mbm-dialer/app/public/leads_database.json   verified prospect pool
Anything without an underlying event row = 0.
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from MBM.LeadEngine import outreach_event as oe  # noqa: E402


def main() -> int:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = ROOT / "MBM" / "Artifacts" / "GTM" / "daily" / today
    out_dir.mkdir(parents=True, exist_ok=True)

    db = json.loads((ROOT / "mbm-dialer/app/public/leads_database.json").read_text(encoding="utf-8"))
    recs = db if isinstance(db, list) else db.get("records", [])
    verified = len(recs)
    callable_n = sum(1 for r in recs if r.get("callable"))

    events = oe.load_events()
    fc = oe.funnel_counts(events)

    whop_path = ROOT / "MBM" / "Whop" / "logs" / "revenue_events.jsonl"
    checkout_clicks = 0
    payments = 0.0
    if whop_path.exists():
        for line in whop_path.read_text(encoding="utf-8").splitlines():
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            name = str(ev.get("event_name") or "").lower()
            if name in ("checkout_click", "cta_click"):
                checkout_clicks += 1
            if name == "payment_received":
                payments += float(ev.get("amount_usd") or 0)

    offers = fc.get("offers_sent", 0)
    appointments = fc.get("appointments", 0)

    board = {
        "report": "revenue_scoreboard",
        "date": today,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "law": "no_event = zero; every number traces to an event row or DB count",
        "verified_prospects": verified,
        "call_ready": callable_n,
        "calls_attempted": fc.get("calls_attempted", 0),
        "connections": fc.get("connected", 0),
        "conversations": fc.get("conversations", 0),
        "wrong_numbers": fc.get("wrong_numbers", 0),
        "wrong_parties": fc.get("wrong_parties", 0),
        "followups": 0,
        "offers": offers,
        "appointments": appointments,
        "checkout_clicks": checkout_clicks,
        "payments": 1 if payments > 0 else 0,
        "revenue_usd": round(payments, 2),
        "telephony_infra": {
            "status": "BLOCKED_ACCOUNT_LEVEL",
            "detail": ("Twilio TRIAL: live_calls_unlocked=false; sole listed "
                       "caller-id rejected as unverified on dial attempt "
                       "(HTTP 400). Requires owner billing upgrade + number "
                       "re-verification before any outbound sprint."),
            "evidence": "preflight 2026-08-26 + TwilioRestException 400",
        },
        "event_store_counts": {"outreach_events": len(events)},
    }
    path = out_dir / "revenue_scoreboard.json"
    path.write_text(json.dumps(board, indent=2), encoding="utf-8")
    print(f"WROTE {path}")
    print(json.dumps({k: v for k, v in board.items()
                      if k not in ("telephony_infra",)}, indent=2)[:600])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
