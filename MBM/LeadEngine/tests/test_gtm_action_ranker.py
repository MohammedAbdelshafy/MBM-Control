"""
TESTS: GTM ACTION RANKER & CHANNEL ROUTER
=================================================================================================================
Hermetic unit tests verifying:
1. Highest-value action wins (deterministic priority ordering)
2. Suppression penalty (hard zero, garbage never recycled)
3. Staleness penalty (>14d / >30d decay)
4. Confidence penalty (low confidence discounted)
5. Duplicate-action penalty (same action re-queued)
6. Missing-evidence penalty (zero-fabrication gate)
7. Identity confirmation boosts priority (OWNER_CONFIRMED > IDENTITY_UNCONFIRMED)
8. Channel Router chooses the smallest useful next action
=================================================================================================================
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.gtm.action_ranker import ActionRanker, ChannelRouter, ChannelType, ActionType


def _base_opp(**overrides) -> dict:
    opp = {
        "id": "OPP-BASE",
        "expected_revenue": 3500.0,
        "intent_score": 90.0,
        "urgency": 1.0,
        "confidence": 0.9,
        "signal_age_days": 2,
        "recent_attempts": 0,
        "duplicate_touch_count": 0,
        "phone": "+12148849120",
        "email": "owner@example.com",
        "evidence": {"source": "LinkedIn Public Post", "source_reference": "https://example.com/sig"},
        "state": "QUALIFIED",
        "identity_state": "IDENTITY_UNCONFIRMED",
    }
    opp.update(overrides)
    return opp


def test_highest_value_action_wins():
    """Verify the ranker picks the highest-revenue, most-confident action first."""
    ranker = ActionRanker()
    low = _base_opp(expected_revenue=1500.0, confidence=0.6, intent_score=60.0)
    high = _base_opp(expected_revenue=8000.0, confidence=0.95, intent_score=95.0)

    ranked = ranker.rank_opportunities([low, high])
    assert ranked[0].entity_id == high["id"]
    assert ranked[0].priority > ranked[1].priority


def test_suppression_penalty_is_hard_zero():
    """Verify suppressed opportunities score exactly 0.0 and are excluded."""
    ranker = ActionRanker()
    suppressed = _base_opp(is_suppressed=True)
    assert ranker.calculate_priority_score(suppressed) == 0.0

    ranked = ranker.rank_opportunities([suppressed])
    assert ranked == []


def test_suppressive_identity_state_is_hard_zero():
    """Verify WRONG_PERSON / WRONG_NUMBER / TENANT identity states score 0.0."""
    ranker = ActionRanker()
    for bad in ("WRONG_PERSON", "WRONG_NUMBER", "TENANT", "DO_NOT_CALL", "QUARANTINED"):
        opp = _base_opp(identity_state=bad)
        assert ranker.calculate_priority_score(opp) == 0.0, f"expected 0.0 for {bad}"


def test_stale_penalty():
    """Verify stale signals (>30 days) score lower than fresh signals."""
    ranker = ActionRanker()
    fresh = _base_opp(signal_age_days=2)
    stale = _base_opp(signal_age_days=35)

    s_fresh = ranker.calculate_priority_score(fresh)
    s_stale = ranker.calculate_priority_score(stale)
    assert s_stale < s_fresh


def test_confidence_penalty():
    """Verify low confidence (<0.70) is discounted."""
    ranker = ActionRanker()
    confident = _base_opp(confidence=0.95)
    unsure = _base_opp(confidence=0.50)

    s_conf = ranker.calculate_priority_score(confident)
    s_unsure = ranker.calculate_priority_score(unsure)
    assert s_unsure < s_conf


def test_duplicate_action_penalty():
    """Verify repeatedly queued identical actions are penalized."""
    ranker = ActionRanker()
    fresh = _base_opp(duplicate_touch_count=0)
    duplicated = _base_opp(duplicate_touch_count=4)

    s_fresh = ranker.calculate_priority_score(fresh)
    s_dup = ranker.calculate_priority_score(duplicated)
    assert s_dup < s_fresh


def test_missing_evidence_penalty():
    """Verify opportunities without evidence are penalized (zero-fabrication gate)."""
    ranker = ActionRanker()
    with_evidence = _base_opp(evidence={"source": "LinkedIn", "claim": "verified pain"})
    no_evidence = _base_opp(evidence=None)

    s_ev = ranker.calculate_priority_score(with_evidence)
    s_no = ranker.calculate_priority_score(no_evidence)
    assert s_no < s_ev


def test_recent_failed_contact_penalty():
    """Verify repeated failed contact attempts reduce priority."""
    ranker = ActionRanker()
    fresh = _base_opp(recent_attempts=0)
    failed = _base_opp(recent_attempts=4)

    s_fresh = ranker.calculate_priority_score(fresh)
    s_failed = ranker.calculate_priority_score(failed)
    assert s_failed < s_fresh


def test_owner_confirmed_boosts_priority():
    """Verify OWNER_CONFIRMED identity state raises priority over unconfirmed."""
    ranker = ActionRanker()
    unconfirmed = _base_opp(identity_state="IDENTITY_UNCONFIRMED")
    confirmed = _base_opp(identity_state="OWNER_CONFIRMED")

    s_un = ranker.calculate_priority_score(unconfirmed)
    s_cf = ranker.calculate_priority_score(confirmed)
    assert s_cf > s_un


def test_every_recommended_action_has_evidence():
    """Verify every ranked action carries the required evidence field."""
    ranker = ActionRanker()
    opps = [
        _base_opp(id="A1", expected_revenue=6000.0),
        _base_opp(id="A2", expected_revenue=2500.0),
    ]
    for action in ranker.rank_opportunities(opps):
        assert action.evidence, "action missing evidence"
        assert "UNKNOWN" not in str(action.evidence.get("source"))


def test_channel_router_smallest_useful_action():
    """Verify the router picks a single smallest useful channel per state."""
    # Qualified with phone -> PHONE call
    ch, act = ChannelRouter.route(_base_opp(state="QUALIFIED", phone="+12148849120"))
    assert ch == ChannelType.PHONE
    assert act == ActionType.CALL_DISCOVERY

    # Qualified, phone only -> never multi-channel automatically
    ch, act = ChannelRouter.route(_base_opp(state="QUALIFIED", phone="+12148849120", email=""))
    assert ch == ChannelType.PHONE

    # Engaged -> BOOK_MEETING
    ch, act = ChannelRouter.route(_base_opp(state="ENGAGED"))
    assert ch in {ChannelType.MEETING, ChannelType.PHONE}

    # Suppressed -> SUPPRESS_LEAD on NONE channel
    ch, act = ChannelRouter.route(_base_opp(is_suppressed=True))
    assert ch == ChannelType.NONE
    assert act == ActionType.SUPPRESS_LEAD

    # Wrong person -> HUMAN_REVIEW / SUPPRESS_LEAD
    ch, act = ChannelRouter.route(_base_opp(identity_state="WRONG_PERSON"))
    assert ch == ChannelType.HUMAN_REVIEW
    assert act == ActionType.SUPPRESS_LEAD

    # NURTURE -> NURTURE
    ch, act = ChannelRouter.route(_base_opp(state="NURTURE"))
    assert ch == ChannelType.NURTURE
    assert act == ActionType.NURTURE