#!/usr/bin/env python3
"""
Hermetic ordering tests for the canonical dialer queue engine.

Controlled case (the bug that motivated the fix): a fresh lead with a lower
composite score must outrank an old lead with a higher score:
    NEW_A(prio 80), NEW_B(prio 70), OLD_A(prio 99)  ->  NEW_A, NEW_B, OLD_A
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.dialer_queue_engine import (
    build_global_queue,
    get_callable_state,
    rank_main_queue,
)


def make_lead(overrides):
    now = datetime.now(timezone.utc)
    lead = {
        "id": "LEAD",
        "contact": "Elena Vasquez",
        "phone": "+18179924401",
        "skip_trace_status": "VERIFIED",
        "intent_score": 90,
        "motivation_score": 90,
        "deal_score": 90,
        "callability_score": 90,
        "attempts": 0,
        "imported_at": now.isoformat(),
        "verified_at": now.isoformat(),
        "discovered_at": now.isoformat(),
    }
    lead.update(overrides)
    return lead


def test_controlled_case_freshness_beats_raw_score():
    now = datetime.now(timezone.utc)
    new_a = make_lead({"id": "NEW_A", "contact": "Alice Adams", "phone": "+18179924401",
                       "intent_score": 80, "motivation_score": 80, "deal_score": 80,
                       "priority_score": 80, "freshness_score": 95})
    new_b = make_lead({"id": "NEW_B", "contact": "Bob Baker", "phone": "+19726658140",
                       "intent_score": 70, "motivation_score": 70, "deal_score": 70,
                       "priority_score": 70, "freshness_score": 95})
    old_a = make_lead({"id": "OLD_A", "contact": "Carol Clark", "phone": "+17572471065",
                       "intent_score": 99, "motivation_score": 99, "deal_score": 99,
                       "priority_score": 99, "freshness_score": 25,
                       "imported_at": (now - timedelta(days=90)).isoformat(),
                       "verified_at": (now - timedelta(days=90)).isoformat(),
                       "discovered_at": (now - timedelta(days=90)).isoformat()})

    ranked = rank_main_queue([old_a, new_b, new_a])
    assert [l["id"] for l in ranked] == ["NEW_A", "NEW_B", "OLD_A"], ranked

    states = {l["id"]: get_callable_state(l) for l in ranked}
    assert states["NEW_A"]["freshness_stage"] == "NEWLY_IMPORTED"
    assert states["NEW_B"]["freshness_stage"] == "NEWLY_IMPORTED"
    assert states["OLD_A"]["freshness_stage"] == "OLD"
    assert all(s["main_queue"] for s in states.values())


def test_global_queue_partition_preserves_controlled_order():
    now = datetime.now(timezone.utc)
    new_a = make_lead({"id": "NEW_A", "contact": "Alice Adams", "phone": "+18179924401",
                       "intent_score": 80, "motivation_score": 80, "deal_score": 80,
                       "priority_score": 80, "freshness_score": 95})
    new_b = make_lead({"id": "NEW_B", "contact": "Bob Baker", "phone": "+19726658140",
                       "intent_score": 70, "motivation_score": 70, "deal_score": 70,
                       "priority_score": 70, "freshness_score": 95})
    old_a = make_lead({"id": "OLD_A", "contact": "Carol Clark", "phone": "+17572471065",
                       "intent_score": 99, "motivation_score": 99, "deal_score": 99,
                       "priority_score": 99, "freshness_score": 25,
                       "imported_at": (now - timedelta(days=90)).isoformat(),
                       "verified_at": (now - timedelta(days=90)).isoformat(),
                       "discovered_at": (now - timedelta(days=90)).isoformat()})

    buckets = build_global_queue([old_a, new_b, new_a], call_now_size=25, next_size=75)
    call_now = buckets["FRESH_CALL_NOW"]
    assert [l["id"] for l in call_now] == ["NEW_A", "NEW_B", "OLD_A"], call_now
    assert all(l["queue_bucket"] == "FRESH_CALL_NOW" for l in call_now)
    assert [l["priority_rank"] for l in call_now] == [1, 2, 3]


if __name__ == "__main__":
    test_controlled_case_freshness_beats_raw_score()
    test_global_queue_partition_preserves_controlled_order()
    print("test_dialer_freshness_ordering.py: all assertions passed")