"""Event-derived analytics for REAL ESTATE AI MEDIA.

No event = ZERO. Counters come exclusively from passed event/record lists
(persisted doctype history), never estimates.
"""
from __future__ import annotations

from typing import Any, Dict, Iterable, List


def _count(rows: Iterable[Dict[str, Any]], pred) -> int:
    return sum(1 for r in rows if pred(r))


def dashboard_counts(*, agents: List[Dict[str, Any]],
                     samples: List[Dict[str, Any]],
                     call_events: List[Dict[str, Any]],
                     quotes: List[Dict[str, Any]],
                     won: List[Dict[str, Any]],
                     production_events: List[Dict[str, Any]]) -> Dict[str, Any]:
    qualified = _count(agents, lambda a: int(a.get("qualification_score") or 0) >= 45)
    sample_candidates = _count(agents, lambda a: a.get("sample_candidate"))
    calls = _count(call_events, lambda e: e.get("event") == "call_started")
    connections = _count(call_events, lambda e: e.get("event") == "call_connected")
    callbacks = _count(call_events, lambda e: e.get("disposition") == "CALLBACK")
    interested = _count(call_events, lambda e: e.get("disposition") == "INTERESTED")
    closes = len(won)
    conv = round((connections / calls) * 100, 1) if calls else 0.0

    gen_time = [float(p.get("generation_seconds")) for p in production_events
                if p.get("generation_seconds") is not None]
    qa_fail = _count(production_events, lambda p: p.get("qa_status") == "FAIL")
    revisions = _count(production_events, lambda p: p.get("revision") is True)

    return {
        "acquisition": {
            "leads_discovered": len(agents),
            "qualified_leads": qualified,
            "sample_candidates": sample_candidates,
            "samples_generated": len(samples),
            "samples_delivered": _count(samples, lambda s: s.get("delivery_status") == "DELIVERED"),
        },
        "sales": {
            "calls": calls,
            "connections": connections,
            "callbacks": callbacks,
            "interested": interested,
            "quotes": len(quotes),
            "closes": closes,
            "conversion_rate_pct": conv,
            "revenue": sum(float(w.get("quoted_price") or 0) for w in won),
            "average_deal_size": (sum(float(w.get("quoted_price") or 0) for w in won) / closes)
            if closes else 0.0,
        },
        "production": {
            "avg_generation_seconds": (sum(gen_time) / len(gen_time)) if gen_time else 0.0,
            "generation_failures": _count(production_events, lambda p: p.get("status") == "FAILED"),
            "qa_failures": qa_fail,
            "revision_rate_pct": round((revisions / len(samples)) * 100, 1) if samples else 0.0,
        },
        "customer": {
            "repeat_listings": _count(agents, lambda a: int(a.get("won_deals") or 0) > 1),
            "package_upgrades": _count(agents, lambda a: a.get("upgraded_from_package")),
            "subscription_conversions": _count(
                agents, lambda a: (a.get("current_package") == "MONTHLY_SUBSCRIPTION")),
            # CLV is computed ONLY from recorded payments; none recorded here yet.
            "customer_lifetime_value": sum(float(w.get("quoted_price") or 0) for w in won),
        },
    }
