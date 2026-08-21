#!/usr/bin/env python3
"""
Hermetic ordering tests for the canonical dialer queue engine.

Controlled case (the bug that motivated the fix): a fresh lead with a lower
composite score must outrank an old lead with a higher score:
    NEW_A(prio 80), NEW_B(prio 70), OLD_A(prio 99)  ->  NEW_A, NEW_B, OLD_A

Newest-first invariant suite (canonical ordering mission):
    Within every niche/vertical/filter, ordering is
        freshness stage -> ingestion timestamp DESC -> priority tiebreaker.
    A genuinely newer lead displaces older leads immediately; static scores,
    stale ranks, and array positions can never override ingestion freshness.
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
    ingestion_timestamp_of,
    rank_main_queue,
)


def make_lead(overrides):
    now = datetime.now(timezone.utc)
    lead = {
        "id": "LEAD",
        "contact": "Elena Vasquez",
        "phone": "+18179924499",
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


def _phone(i: int) -> str:
    """Unique gate-valid NANP phone: +1817992XXXX."""
    return f"+1817992{i % 10000:04d}"


def _ts(minutes_ago: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)).isoformat()


def build_mixed_fixture():
    """100 old + 20 recent + 10 new eligible leads + 5 duplicates + 3 suppressed,
    spread across 3 niches (HEALTHCARE_CLINIC, AI_CONSULTANCY, CONTRACTOR)."""
    leads = []
    n = 0
    # 10 NEW leads (minutes old), rotated across niches
    for i in range(10):
        leads.append(make_lead({
            "id": f"NEW-{i:03d}", "phone": _phone(n := n + 1),
            "company": f"Fresh Co {i}", "vertical": ["Dental Clinics", "AI Consultancy", "Commercial Contractors"][i % 3],
            "priority_score": 50 + i, "freshness_score": 95,
            "imported_at": _ts(5 + i), "discovered_at": _ts(5 + i),
            "first_seen_at": _ts(5 + i), "created_at": _ts(5 + i),
            "verified_at": _ts(5 + i),
        }))
    # 20 RECENT leads (~1 day old), lower scores than some OLD leads
    for i in range(20):
        leads.append(make_lead({
            "id": f"REC-{i:03d}", "phone": _phone(n := n + 1),
            "company": f"Recent Co {i}", "vertical": ["Dental Clinics", "AI Consultancy", "Commercial Contractors"][i % 3],
            "priority_score": 40 + i, "freshness_score": 60,
            "imported_at": _ts(60 * 24 + i), "discovered_at": _ts(60 * 24 + i),
            "first_seen_at": _ts(60 * 24 + i), "created_at": _ts(60 * 24 + i),
            "verified_at": _ts(60 * 24 + i),
        }))
    # 100 OLD leads (~120 days old); give several VERY high static scores
    for i in range(100):
        leads.append(make_lead({
            "id": f"OLD-{i:03d}", "phone": _phone(n := n + 1),
            "company": f"Old Co {i}", "vertical": ["Dental Clinics", "AI Consultancy", "Commercial Contractors"][i % 3],
            "priority_score": 99 if i < 10 else 30, "freshness_score": 25,
            "imported_at": _ts(60 * 24 * 120 + i), "discovered_at": _ts(60 * 24 * 120 + i),
            "first_seen_at": _ts(60 * 24 * 120 + i), "created_at": _ts(60 * 24 * 120 + i),
            "verified_at": _ts(60 * 24 * 120 + i),
        }))
    # 5 DUPLICATES (same company+phone as first 5 NEW leads) — still eligible records
    for i in range(5):
        src = leads[i]
        leads.append(make_lead({
            "id": f"DUP-{i:03d}", "phone": src["phone"],
            "company": src["company"], "vertical": src["vertical"],
            "priority_score": 95, "freshness_score": 95,
            "imported_at": _ts(6 + i), "discovered_at": _ts(6 + i),
            "first_seen_at": _ts(6 + i), "created_at": _ts(6 + i),
            "verified_at": _ts(6 + i),
        }))
    # 3 SUPPRESSED (DNC) — one of them brand new: safety ALWAYS beats freshness
    for i in range(3):
        leads.append(make_lead({
            "id": f"SUP-{i:03d}", "phone": _phone(n := n + 1),
            "company": f"Suppressed Co {i}", "vertical": "Dental Clinics",
            "disposition": "DNC",
            "imported_at": _ts(1), "discovered_at": _ts(1),
            "first_seen_at": _ts(1), "created_at": _ts(1),
            "verified_at": _ts(1),
        }))
    return leads


def _niche(leads, vertical):
    return [l for l in leads if l.get("vertical") == vertical]


def test_newest_first_across_every_niche():
    leads = build_mixed_fixture()
    ranked = rank_main_queue(leads)
    ranked_ids = [l["id"] for l in ranked]

    # No suppressed/DNC lead may ever enter the main queue.
    assert not any(i.startswith("SUP-") for i in ranked_ids)

    for vertical in ("Dental Clinics", "AI Consultancy", "Commercial Contractors"):
        niche_ids = [l["id"] for l in _niche(ranked, vertical)]
        assert niche_ids, vertical
        ing = [ingestion_timestamp_of(l) for l in _niche(ranked, vertical)]
        assert ing == sorted(ing, reverse=True), f"{vertical} not newest-first: {niche_ids[:5]}"
        # First record is a NEW-* lead, never an OLD-* high-score lead.
        assert niche_ids[0].startswith(("NEW-", "DUP-")), (vertical, niche_ids[0])
        # The very last eligible record in the niche is an OLD lead.
        assert niche_ids[-1].startswith("OLD-"), (vertical, niche_ids[-1])

    # Global head of queue = absolute newest eligible lead overall.
    assert ranked_ids[0].startswith("NEW-")
    # Global tail contains only OLD-stage leads.
    assert all(l["_callable_state"]["freshness_stage"] == "OLD" for l in ranked[-5:])


def test_high_old_score_never_beats_newer_lead():
    now = datetime.now(timezone.utc)
    old_high = make_lead({
        "id": "OLD_HIGH", "contact": "Old High Score", "phone": "+17572471065",
        "intent_score": 99, "motivation_score": 99, "deal_score": 99,
        "priority_score": 99, "freshness_score": 25,
        "imported_at": (now - timedelta(days=2)).isoformat(),
        "discovered_at": (now - timedelta(days=2)).isoformat(),
        "first_seen_at": (now - timedelta(days=2)).isoformat(),
        "created_at": (now - timedelta(days=2)).isoformat(),
        "verified_at": (now - timedelta(days=2)).isoformat(),
    })
    new_low = make_lead({
        "id": "NEW_LOW", "contact": "New Low Score", "phone": "+19726658140",
        "intent_score": 41, "motivation_score": 41, "deal_score": 41,
        "priority_score": 41, "freshness_score": 95,
        "imported_at": (now - timedelta(minutes=5)).isoformat(),
        "discovered_at": (now - timedelta(minutes=5)).isoformat(),
        "first_seen_at": (now - timedelta(minutes=5)).isoformat(),
        "created_at": (now - timedelta(minutes=5)).isoformat(),
        "verified_at": (now - timedelta(minutes=5)).isoformat(),
    })
    ranked = rank_main_queue([old_high, new_low])
    assert [l["id"] for l in ranked] == ["NEW_LOW", "OLD_HIGH"], ranked


def test_new_lead_promotes_to_rank_one_within_niche_only():
    leads = build_mixed_fixture()
    ranked_before = rank_main_queue(leads)

    ai_before = [l["id"] for l in _niche(ranked_before, "AI Consultancy")]
    dental_before = [l["id"] for l in _niche(ranked_before, "Dental Clinics")]

    # 1. Insert a brand-new AI Consultancy lead (eligible, modest score).
    newcomer_ai = make_lead({
        "id": "NEWCOMER-AI", "phone": "+18179929991",
        "company": "Brand New AI Co", "vertical": "AI Consultancy",
        "priority_score": 42, "freshness_score": 95,
        "imported_at": _ts(1), "discovered_at": _ts(1),
        "first_seen_at": _ts(1), "created_at": _ts(1),
        "verified_at": _ts(1),
    })
    ranked_after = rank_main_queue(leads + [newcomer_ai])
    ai_after = [l["id"] for l in _niche(ranked_after, "AI Consultancy")]
    assert ai_after[0] == "NEWCOMER-AI", ai_after[:3]
    # Prior AI order preserved beneath the newcomer (stable displacement).
    assert ai_after[1:] == ai_before, (ai_after[:4], ai_before[:4])

    # 2. Insert a second newcomer into a DIFFERENT niche (Dental).
    newcomer_dental = make_lead({
        "id": "NEWCOMER-DEN", "phone": "+18179929992",
        "company": "Brand New Dental Co", "vertical": "Dental Clinics",
        "priority_score": 42, "freshness_score": 95,
        "imported_at": _ts(0.5), "discovered_at": _ts(0.5),
        "first_seen_at": _ts(0.5), "created_at": _ts(0.5),
        "verified_at": _ts(0.5),
    })
    ranked_final = rank_main_queue(leads + [newcomer_ai, newcomer_dental])
    dental_after = [l["id"] for l in _niche(ranked_final, "Dental Clinics")]
    ai_final = [l["id"] for l in _niche(ranked_final, "AI Consultancy")]
    assert dental_after[0] == "NEWCOMER-DEN"
    assert ai_final[0] == "NEWCOMER-AI"  # unrelated niche undisturbed
    assert dental_after[1:] == dental_before


def test_edge_cases_missing_invalid_same_future_timestamps():
    now = datetime.now(timezone.utc)
    base = dict(priority_score=50, freshness_score=95)

    missing_ts = make_lead({"id": "EDGE-MISSING", "phone": "+18179928801",
                            "company": "No Timestamp Co", "vertical": "Niche X",
                            "imported_at": None, "discovered_at": None,
                            "first_seen_at": None, "created_at": None})
    invalid_ts = make_lead({"id": "EDGE-INVALID", "phone": "+18179928802",
                            "company": "Bad Timestamp Co", "vertical": "Niche X",
                            "imported_at": "not-a-date", "discovered_at": "",
                            "first_seen_at": "2026-13-45T99:99:99Z"})
    same_a = make_lead({"id": "EDGE-SAME-A", "phone": "+18179928803",
                        "company": "Same Ts A", "vertical": "Niche X",
                        "imported_at": "2026-08-20T12:00:00+00:00",
                        "first_seen_at": "2026-08-20T12:00:00+00:00"})
    same_b = make_lead({"id": "EDGE-SAME-B", "phone": "+18179928804",
                        "company": "Same Ts B", "vertical": "Niche X",
                        "imported_at": "2026-08-20T07:00:00-05:00",  # same instant, other tz
                        "first_seen_at": "2026-08-20T07:00:00-05:00"})
    future_ts = make_lead({"id": "EDGE-FUTURE", "phone": "+18179928805",
                           "company": "Future Dated Co", "vertical": "Niche X",
                           "imported_at": (now + timedelta(days=1)).isoformat(),
                           "first_seen_at": (now + timedelta(days=1)).isoformat()})
    normal = make_lead({"id": "EDGE-NORMAL", "phone": "+18179928806",
                        "company": "Normal Co", "vertical": "Niche X",
                        "imported_at": _ts(30), "first_seen_at": _ts(30)})

    ranked = rank_main_queue([missing_ts, invalid_ts, same_b, same_a, future_ts, normal])
    ids = [l["id"] for l in ranked]

    # Missing/invalid timestamps land deterministically at the BOTTOM (never crash,
    # never treated as "now"). Full ties resolve by stable ID.
    assert set(ids[-2:]) == {"EDGE-MISSING", "EDGE-INVALID"}, ids
    assert ids[-2:] == sorted(ids[-2:]), ids
    # Future-dated lead sorts first (largest epoch).
    # Canonical order: future > normal(30m) > same-instant pair(yesterday) >
    # invalid/missing (bottom). Same-instant different-timezone leads are
    # adjacent; stable ID breaks the tie.
    assert ids == [
        "EDGE-FUTURE", "EDGE-NORMAL", "EDGE-SAME-A", "EDGE-SAME-B",
        "EDGE-INVALID", "EDGE-MISSING",
    ], ids
    again = [l["id"] for l in rank_main_queue(list(reversed([missing_ts, invalid_ts, same_b, same_a, future_ts, normal])))]
    assert again == ids, (ids, again)


def test_suppressed_and_non_callable_excluded_regardless_of_freshness():
    brand_new_dnc = make_lead({
        "id": "SAFETY-DNC", "phone": "+18179927701",
        "company": "DNC But Brand New", "vertical": "Niche Y",
        "disposition": "DO_NOT_CALL",
        "imported_at": _ts(0.1), "first_seen_at": _ts(0.1),
    })
    # Non-callable via a REAL canonical signal (invalid phone -> verification
    # gate), not an input flag: the engine derives eligibility, never trusts it.
    uncallable = make_lead({
        "id": "SAFETY-UNCALLABLE", "phone": "+10000000000",
        "company": "Uncallable Fresh", "vertical": "Niche Y",
        "imported_at": _ts(0.1), "first_seen_at": _ts(0.1),
    })
    eligible_old = make_lead({
        "id": "SAFETY-ELIGIBLE-OLD", "phone": "+18179927703",
        "company": "Eligible Old", "vertical": "Niche Y",
        "imported_at": _ts(60 * 24 * 30), "first_seen_at": _ts(60 * 24 * 30),
    })
    ranked = rank_main_queue([brand_new_dnc, uncallable, eligible_old])
    ids = [l["id"] for l in ranked]
    assert ids == ["SAFETY-ELIGIBLE-OLD"], ids
    state_dnc = get_callable_state(brand_new_dnc)
    assert state_dnc["queue_bucket"] == "SUPPRESSED"
    state_uncallable = get_callable_state(uncallable)
    assert state_uncallable["queue_bucket"] == "VERIFICATION_REQUIRED"
    assert state_uncallable["main_queue"] is False


def test_pagination_slices_preserve_canonical_order():
    leads = build_mixed_fixture()
    ranked = rank_main_queue(leads)  # FILTER -> SORT once
    page_size = 25
    pages = [ranked[i:i + page_size] for i in range(0, len(ranked), page_size)]

    # Page 1 holds the newest leads; each later page continues chronologically down.
    first_ing = ingestion_timestamp_of(pages[0][0])
    last_ing = ingestion_timestamp_of(pages[-1][-1])
    assert first_ing > last_ing

    flat = [l["id"] for page in pages for l in page]
    assert flat == [l["id"] for l in ranked]  # pagination never reorders

    # Navigating pages does not reset sorting: page k+1 head is older than page k tail.
    for a, b in zip(pages, pages[1:]):
        assert ingestion_timestamp_of(a[-1]) >= ingestion_timestamp_of(b[0])


def test_empty_niche_and_duplicate_phones_are_stable():
    empty = rank_main_queue([])
    assert empty == []

    dup_a = make_lead({"id": "DUPPHONE-A", "phone": "+18179926601",
                       "company": "Same Company Inc", "vertical": "Niche Z",
                       "imported_at": _ts(10), "first_seen_at": _ts(10)})
    dup_b = make_lead({"id": "DUPPHONE-B", "phone": "+18179926601",
                       "company": "Same Company Inc", "vertical": "Niche Z",
                       "imported_at": _ts(10), "first_seen_at": _ts(10)})
    newer = make_lead({"id": "DUPPHONE-NEW", "phone": "+18179926602",
                       "company": "Same Company Inc", "vertical": "Niche Z",
                       "imported_at": _ts(2), "first_seen_at": _ts(2)})
    ranked = rank_main_queue([dup_a, dup_b, newer])
    ids = [l["id"] for l in ranked]
    assert ids[0] == "DUPPHONE-NEW"
    assert set(ids[1:]) == {"DUPPHONE-A", "DUPPHONE-B"}  # deterministic tie by ID
    assert ids[1:] == sorted(ids[1:])


if __name__ == "__main__":
    test_controlled_case_freshness_beats_raw_score()
    test_global_queue_partition_preserves_controlled_order()
    test_newest_first_across_every_niche()
    test_high_old_score_never_beats_newer_lead()
    test_new_lead_promotes_to_rank_one_within_niche_only()
    test_edge_cases_missing_invalid_same_future_timestamps()
    test_suppressed_and_non_callable_excluded_regardless_of_freshness()
    test_pagination_slices_preserve_canonical_order()
    test_empty_niche_and_duplicate_phones_are_stable()
    print("test_dialer_freshness_ordering.py: all assertions passed")


def test_controlled_case_freshness_beats_raw_score():
    now = datetime.now(timezone.utc)
    # Explicit distinct ingestion timestamps: NEW_A newest, NEW_B next, OLD_A ancient.
    new_a = make_lead({"id": "NEW_A", "contact": "Alice Adams", "phone": "+18179924499",
                       "intent_score": 80, "motivation_score": 80, "deal_score": 80,
                       "priority_score": 80, "freshness_score": 95,
                       "imported_at": (now - timedelta(minutes=5)).isoformat(),
                       "discovered_at": (now - timedelta(minutes=5)).isoformat()})
    new_b = make_lead({"id": "NEW_B", "contact": "Bob Baker", "phone": "+19726658140",
                       "intent_score": 70, "motivation_score": 70, "deal_score": 70,
                       "priority_score": 70, "freshness_score": 95,
                       "imported_at": (now - timedelta(minutes=10)).isoformat(),
                       "discovered_at": (now - timedelta(minutes=10)).isoformat()})
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
    new_a = make_lead({"id": "NEW_A", "contact": "Alice Adams", "phone": "+18179924499",
                       "intent_score": 80, "motivation_score": 80, "deal_score": 80,
                       "priority_score": 80, "freshness_score": 95,
                       "imported_at": (now - timedelta(minutes=5)).isoformat(),
                       "discovered_at": (now - timedelta(minutes=5)).isoformat()})
    new_b = make_lead({"id": "NEW_B", "contact": "Bob Baker", "phone": "+19726658140",
                       "intent_score": 70, "motivation_score": 70, "deal_score": 70,
                       "priority_score": 70, "freshness_score": 95,
                       "imported_at": (now - timedelta(minutes=10)).isoformat(),
                       "discovered_at": (now - timedelta(minutes=10)).isoformat()})
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