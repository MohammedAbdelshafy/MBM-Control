"""
whop_revenue_copilot.py — Revenue Copilot (evidence-cited answers)
===================================================================
Answers the canonical revenue questions against repository evidence.
Every answer cites the files it read. Nothing is fabricated; missing
evidence is reported as UNAVAILABLE.

Usage:
  python MBM/Whop/whop_revenue_copilot.py                 # all questions
  python MBM/Whop/whop_revenue_copilot.py what-made-money
  python MBM/Whop/whop_revenue_copilot.py leaks
  python MBM/Whop/whop_revenue_copilot.py ready-to-buy
  python MBM/Whop/whop_revenue_copilot.py at-risk
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import whop_revenue_os as ros  # noqa: E402


def _cite(*paths):
    return [str(p) for p in paths]


def what_made_money() -> dict:
    rev = ros.revenue_summary()
    cat = ros.load_catalog()
    return {
        "question": "What made money?",
        "answer": (f"{rev['orders']} orders, ${rev['gross_revenue_usd']} gross "
                   f"(refunds ${rev['refunds_usd']})") if rev["orders"] else
                  "No purchases recorded yet — the store has 0 members. UNAVAILABLE.",
        "provenance": rev["provenance"],
        "live_products": [{"id": p.get("key"), "name": p.get("name"),
                           "members": p.get("live_member_count", "n/a")}
                          for p in cat["products"]],
        "evidence": _cite(ros.EVENTS_FILE, ros.REVENUE_REPORT, ros.PRODUCT_SPEC),
    }


def what_changed() -> dict:
    events = ros.load_events()
    by_day = {}
    for e in events:
        day = str(e.get("timestamp", ""))[:10]
        by_day.setdefault(day, {}).setdefault(e["event_name"], 0)
        by_day[day][e["event_name"]] += 1
    return {
        "question": "What changed?",
        "answer": f"{len(events)} canonical events across {len(by_day)} days",
        "daily_breakdown": dict(sorted(by_day.items())[-14:]),
        "provenance": "DERIVED",
        "evidence": _cite(ros.EVENTS_FILE),
    }


def leaks() -> dict:
    funnel = ros.compute_funnel()
    ops = ros.identify_revenue_opportunities()
    leak_ops = [o for o in ops if "leak" in o["type"] or o["type"] == "abandoned_checkout_recovery"]
    worst = None
    rates = funnel["step_rates"]
    if rates:
        worst_step = min(rates, key=rates.get)
        worst = {"step": worst_step, "rate": rates[worst_step]}
    return {
        "question": "Where is revenue leaking?",
        "answer": f"{len(leak_ops)} active leaks" if leak_ops else
                  "Not enough traffic data to isolate a leak yet (UNAVAILABLE).",
        "weakest_funnel_step": worst,
        "opportunities": leak_ops,
        "provenance": "DERIVED",
        "evidence": _cite(ros.EVENTS_FILE),
    }


def ready_to_buy() -> dict:
    customers = ros.build_customer_360()
    sellers = []
    for c in customers:
        nba = c.get("next_best_action") or {}
        if nba.get("action") in ("SELL", "UPSELL"):
            if nba.get("in_cooldown") or nba.get("attempt_limit_reached"):
                continue  # anti-fatigue: never surface cooled/limited contacts
            offers = ros.match_offer(c)
            sellers.append({
                "customer_id": c["identity"]["customer_id"],
                "action": nba["action"],
                "offer": offers[0]["title"] if offers else "UNAVAILABLE",
                "checkout_url": (offers[0].get("checkout_url") if offers else None),
                "confidence": nba.get("confidence"),
                "governor_level": nba.get("governor_level"),
            })
    return {
        "question": "Who is ready to buy / be upsold?",
        "answer": f"{len(sellers)} actionable contacts (cooldowns respected)" if sellers
                  else "No contacts currently eligible (store pre-revenue) — UNAVAILABLE.",
        "contacts": sellers,
        "provenance": "DERIVED",
        "evidence": _cite(ros.MEMBERSHIPS_LEDGER, ros.EVENTS_FILE, ros.ENGAGE_LOG),
    }


def at_risk() -> dict:
    customers = ros.build_customer_360()
    risky = [{"customer_id": c["identity"]["customer_id"],
              "lifecycle_state": c["lifecycle_state"],
              "health_score": c["health_score"],
              "health_reasons": c["health_reasons"],
              "churn_risk": c["churn_risk"]}
             for c in customers
             if c["lifecycle_state"] in ("AT_RISK", "DORMANT", "CANCELLED")
             or (c["health_score"] or 100) < 50]
    engage = {}
    if ros.ENGAGE_LOG.exists():
        try:
            engage = json.loads(ros.ENGAGE_LOG.read_text(encoding="utf-8"))
        except Exception:
            engage = {}
    return {
        "question": "Who is at risk?",
        "answer": f"{len(risky)} at-risk/dormant/churned tracked" if risky else
                  "No memberships tracked yet — UNAVAILABLE.",
        "customers": risky,
        "engage_bot_state": {"actions": engage.get("actions_summary"),
                             "last_updated": engage.get("updated_at")},
        "provenance": "REAL" if risky else "UNAVAILABLE",
        "evidence": _cite(ros.MEMBERSHIPS_LEDGER, ros.ENGAGE_LOG),
    }


def what_to_test() -> dict:
    reg_file = ros.DATA_DIR / "experiments.json"
    running = []
    if reg_file.exists():
        try:
            reg = json.loads(reg_file.read_text(encoding="utf-8"))
            for eid, e in reg.get("experiments", {}).items():
                la = e.get("last_analysis") or {}
                running.append({"id": eid, "verdict": la.get("verdict", "NOT_ANALYZED"),
                                "hypothesis": e.get("hypothesis")})
        except Exception:
            pass
    suggestions = [
        {"surface": "landing headline", "why": "existing client-side split has no server-side attribution",
         "next": "register headline_test_v1 via whop_experiments.py + send landing_variant in analytics"},
        {"surface": "audit CTA price anchor", "why": "$297 entry is the only one-time offer",
         "next": "test $149 triage-audit variant once >=100 views/day captured"},
    ]
    return {
        "question": "What should we test?",
        "answer": running or suggestions,
        "running_experiments": running,
        "suggestions": suggestions,
        "provenance": "DERIVED",
        "evidence": _cite(reg_file),
    }


def fix_first() -> dict:
    ops = ros.identify_revenue_opportunities()
    top = ops[:3] if ops else []
    qa_path = BASE_DIR / "whop_revenue_qa.py"
    return {
        "question": "What should we fix first?",
        "answer": top or ["Run `npm run whop:test` and `python MBM/Whop/whop_revenue_qa.py` — "
                          "with zero members, infrastructure correctness outranks optimization."],
        "ranked_fixes": [{"type": o["type"], "priority": o["priority"],
                          "recommended_action": o["recommended_action"]} for o in top],
        "provenance": "DERIVED",
        "evidence": _cite(ros.EVENTS_FILE, qa_path),
    }


QUESTIONS = {
    "what-made-money": what_made_money,
    "what-changed": what_changed,
    "leaks": leaks,
    "ready-to-buy": ready_to_buy,
    "upsell": ready_to_buy,
    "at-risk": at_risk,
    "what-to-test": what_to_test,
    "fix-first": fix_first,
}


def run_all() -> dict:
    return {name: fn() for name, fn in QUESTIONS.items()}


if __name__ == "__main__":
    key = sys.argv[1] if len(sys.argv) > 1 else None
    payload = QUESTIONS[key]() if key in QUESTIONS else run_all()
    payload.setdefault("generated_at", datetime.now(timezone.utc).isoformat())
    try:
        print(json.dumps(payload, indent=2))
    except UnicodeEncodeError:
        print(json.dumps(payload, default=str).encode("ascii", "replace").decode())
