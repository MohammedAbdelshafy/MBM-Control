"""
revenue_unit_economics.py — first-delivery cost tracker (Revenue Audit Engine)
=============================================================================
Records the ACTUAL economics of a delivered $149 audit. Until a record exists
for a verified purchase, every field reports UNKNOWN — never an assumption.

Ledger: MBM/Whop/data/unit_economics.jsonl  (append-only)

CLI:
  python MBM/Whop/revenue_unit_economics.py show [purchase_event_id]
  python MBM/Whop/revenue_unit_economics.py record <purchase_event_id> \
      --labor-minutes 95 --ai-cost 0.42 --api-cost 0 --refund 0 \
      [--sale-price 149] [--labor-cost 0]

Payment fee defaults to UNKNOWN unless --payment-fee is provided with evidence.
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
LEDGER = DATA_DIR / "unit_economics.jsonl"
EVENTS_FILE = BASE_DIR / "logs" / "revenue_events.jsonl"

DEFAULT_SALE_PRICE = 149.0  # REAL: live Whop plan plan_Sg0oIq3Tf4rlQ


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _verified_purchase_amount(event_id: str):
    """Return the webhook purchase amount for event_id, or None if unverified."""
    if not EVENTS_FILE.exists():
        return None
    for line in EVENTS_FILE.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        if e.get("event_id") == event_id and e.get("event_name") == "purchase" \
                and e.get("source") == "whop_webhook" \
                and not str(event_id).startswith("smoke_"):
            amt = e.get("amount_usd")
            return float(amt) if isinstance(amt, (int, float)) else None
    return None


def blank() -> dict:
    return {
        "schema_version": 1,
        "purchase_event_id": None,
        "classification": "UNKNOWN",
        "sale_price": "UNKNOWN",
        "payment_fee": "UNKNOWN",
        "AI_cost": "UNKNOWN",
        "API_cost": "UNKNOWN",
        "labor_minutes": "UNKNOWN",
        "labor_cost": "UNKNOWN",
        "delivery_cost": "UNKNOWN",
        "refund": "UNKNOWN",
        "net_revenue": "UNKNOWN",
        "gross_margin": "UNKNOWN",
        "provenance": "NO_FIRST_DELIVERY_EVIDENCE",
        "updated_at": _now(),
    }


def compute(record: dict) -> dict:
    """Fill net_revenue/gross_margin ONLY from recorded actuals; else UNKNOWN."""
    r = dict(record)
    numeric = all(isinstance(r.get(k), (int, float))
                  for k in ("sale_price", "payment_fee", "AI_cost", "API_cost",
                            "delivery_cost", "refund"))
    if numeric:
        labor = r.get("labor_cost")
        if isinstance(labor, (int, float)):
            net = r["sale_price"] - r["payment_fee"] - r["AI_cost"] - r["API_cost"] \
                - r["delivery_cost"] - r["refund"] - labor
            r["net_revenue"] = round(net, 2)
            r["gross_margin"] = (f"{round(100 * net / r['sale_price'], 1)}%"
                                 if r["sale_price"] else "UNDEFINED")
        else:
            r["net_revenue"] = "UNKNOWN"
            r["gross_margin"] = "UNKNOWN"
    else:
        r["net_revenue"] = "UNKNOWN"
        r["gross_margin"] = "UNKNOWN"
    return r


def show(purchase_event_id: str | None = None) -> dict:
    rows = []
    if LEDGER.exists():
        for line in LEDGER.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if purchase_event_id:
        match = [r for r in rows if r.get("purchase_event_id") == purchase_event_id]
        out = match[-1] if match else {"error": f"no economics record for {purchase_event_id}"}
    elif rows:
        out = rows[-1]
    else:
        out = blank()
    payload = {"status": "success",
               "outputs": out,
               "errors": [],
               "next_action": ("capture actuals at delivery via 'record'" if rows
                               else "WAITING_FOR_FIRST_VERIFIED_DELIVERY"),
               "owner": "system",
               "timestamp": _now()}
    print(json.dumps(payload, indent=2, default=str))
    return out


def record(purchase_event_id: str, sale_price=None, payment_fee="UNKNOWN",
           ai_cost="UNKNOWN", api_cost="UNKNOWN", labor_minutes="UNKNOWN",
           labor_cost="UNKNOWN", delivery_cost=0.0, refund=0.0) -> dict:
    verified = _verified_purchase_amount(purchase_event_id)
    if verified is None:
        raise SystemExit(
            f"REFUSED: '{purchase_event_id}' is not a verified non-smoke webhook "
            f"purchase in {EVENTS_FILE.name}. Economics attach to real money only.")
    rec = {
        "schema_version": 1,
        "purchase_event_id": purchase_event_id,
        "classification": "REAL",
        "sale_price": float(sale_price) if sale_price is not None else verified,
        "payment_fee": payment_fee,
        "AI_cost": ai_cost,
        "API_cost": api_cost,
        "labor_minutes": labor_minutes,
        "labor_cost": labor_cost,
        "delivery_cost": delivery_cost,
        "refund": refund,
        "recorded_at": _now(),
    }
    rec = compute(rec)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(LEDGER, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, default=str) + "\n")
    print(json.dumps({"status": "success", "outputs": rec, "errors": [],
                      "next_action": "review gross_margin; feed pricing decisions",
                      "owner": "human", "timestamp": _now()}, indent=2, default=str))
    return rec


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("show")
    s.add_argument("purchase_event_id", nargs="?", default=None)
    r = sub.add_parser("record")
    r.add_argument("purchase_event_id")
    r.add_argument("--sale-price", type=float, default=None)
    r.add_argument("--payment-fee", default="UNKNOWN")
    r.add_argument("--ai-cost", dest="ai_cost", default="UNKNOWN")
    r.add_argument("--api-cost", dest="api_cost", default="UNKNOWN")
    r.add_argument("--labor-minutes", dest="labor_minutes", default="UNKNOWN")
    r.add_argument("--labor-cost", dest="labor_cost", default="UNKNOWN")
    r.add_argument("--delivery-cost", dest="delivery_cost", type=float, default=0.0)
    r.add_argument("--refund", type=float, default=0.0)
    args = ap.parse_args()
    if args.cmd == "show":
        show(args.purchase_event_id)
    else:
        record(args.purchase_event_id, sale_price=args.sale_price,
               payment_fee=args.payment_fee, ai_cost=args.ai_cost,
               api_cost=args.api_cost, labor_minutes=args.labor_minutes,
               labor_cost=args.labor_cost, delivery_cost=args.delivery_cost,
               refund=args.refund)


if __name__ == "__main__":
    main()
