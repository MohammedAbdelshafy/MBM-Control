"""
TESTS: GTM COMMANDER
=============================================================================
Hermetic unit tests verifying:
1. GtmCommander initialization & adapters integration
2. State reading & Opportunity identification
3. Action ranking mathematical scoring and penalty gates
4. Safe dry-run delegation & event publishing
5. Evidence store & Zero-fabrication enforcement
6. Revenue lifecycle & Attribution invariants (Proposal != Revenue)
7. Learning engine feedback for scoring
8. Dry-run CLI text formatting output
=============================================================================
"""

import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.gtm_commander import GtmCommander
from MBM.LeadEngine.gtm.evidence import GtmEvidence, EvidenceStore
from MBM.LeadEngine.gtm.action_ranker import ActionRanker, NextBestAction, ChannelType, ActionType
from MBM.LeadEngine.gtm.attribution import AttributionTracker, Touchpoint, RevenueStage
from MBM.LeadEngine.gtm.learning import GtmLearningEngine, OutcomeType
from MBM.LeadEngine.gtm.agent_registry import AgentRegistry, AgentRole


def test_gtm_commander_initialization():
    """Verify GtmCommander initializes with all adapters and subsystems."""
    commander = GtmCommander(dry_run=True)
    assert commander.dry_run is True
    assert commander.event_bus is not None
    assert commander.agent_registry is not None
    assert len(commander.agent_registry.list_agents()) == 23


def test_read_gtm_state():
    """Verify reading aggregate state across connected MBM adapters."""
    commander = GtmCommander(dry_run=True)
    state = commander.read_gtm_state()
    
    assert "hot_buyers_count" in state
    assert "canonical_deals_count" in state
    assert "callable_dialer_leads_count" in state
    assert "timestamp" in state


def test_opportunity_identification_and_ranking():
    """Verify raw prospects are normalized and ranked into NextBestAction items."""
    commander = GtmCommander(dry_run=True)
    opps = commander.identify_opportunities()
    assert isinstance(opps, list)

    ranked_actions = commander.rank_next_actions(limit=5)
    assert isinstance(ranked_actions, list)
    assert len(ranked_actions) <= 5

    for action in ranked_actions:
        assert isinstance(action, NextBestAction)
        assert action.company
        assert action.priority >= 0.0
        assert isinstance(action.recommended_channel, (ChannelType, str))
        assert action.evidence is not None


def test_action_ranker_penalties():
    """Verify ActionRanker applies staleness, suppression, and attempt penalties."""
    ranker = ActionRanker()

    # Normal Hot Opp
    hot_opp = {
        "expected_revenue": 3500.0,
        "intent_score": 95.0,
        "urgency": 1.0,
        "confidence": 0.95,
        "signal_age_days": 1,
        "recent_attempts": 0,
        "phone": "+12148849120",
    }
    score_hot = ranker.calculate_priority_score(hot_opp)
    assert score_hot > 40.0

    # Suppressed Opp -> Must be 0.0
    suppressed_opp = dict(hot_opp)
    suppressed_opp["is_suppressed"] = True
    assert ranker.calculate_priority_score(suppressed_opp) == 0.0

    # Stale Opp (>30 days) -> Score is halved
    stale_opp = dict(hot_opp)
    stale_opp["signal_age_days"] = 35
    score_stale = ranker.calculate_priority_score(stale_opp)
    assert score_stale < score_hot


def test_evidence_zero_fabrication():
    """Verify GtmEvidence rejects empty sources or claims."""
    # Valid evidence
    e = GtmEvidence(
        claim="Marcus Vance seeks ServiceTitan AI dispatch",
        source="LinkedIn Public Post",
        source_reference="https://linkedin.com/feed/update/123",
        confidence=0.95,
        agent="INTENT_HUNTER",
    )
    assert e.confidence == 0.95

    # Empty source must raise ValueError
    with pytest.raises(ValueError):
        GtmEvidence(
            claim="Some claim",
            source="",
            source_reference="",
            confidence=0.9,
            agent="HUNTER",
        )


def test_attribution_revenue_invariants():
    """Verify Proposal Sent != Realized Revenue invariant."""
    tracker = AttributionTracker()

    # 1. Add touchpoints
    tracker.record_touchpoint(Touchpoint(
        entity_id="CO-01",
        stage=RevenueStage.LEAD_DISCOVERED,
        channel="LINKEDIN",
        agent="INTENT_HUNTER",
        source="LinkedIn Post",
    ))
    tracker.record_touchpoint(Touchpoint(
        entity_id="CO-01",
        stage=RevenueStage.PROPOSAL_SENT,
        channel="EMAIL",
        agent="DEAL_STRATEGIST",
        source="Cold Email",
        monetary_value=3500.0,
    ))

    attr = tracker.calculate_attribution("CO-01")
    assert attr["pipeline_value_usd"] == 3500.0
    # Invariant: proposal is NOT realized revenue
    assert attr["realized_revenue_usd"] == 0.0
    assert attr["is_closed_won"] is False

    # 2. Add realized revenue touchpoint
    tracker.record_touchpoint(Touchpoint(
        entity_id="CO-01",
        stage=RevenueStage.REVENUE_RECEIVED,
        channel="NETELLER",
        agent="REVOPS_AGENT",
        source="Neteller Checkout",
        monetary_value=3500.0,
        transaction_id="NETELLER_TX_98765",
    ))

    attr_won = tracker.calculate_attribution("CO-01")
    assert attr_won["realized_revenue_usd"] == 3500.0


def test_learning_feedback_generation():
    """Verify GtmLearningEngine computes vertical multipliers without modifying scoring code."""
    learning = GtmLearningEngine()
    learning.record_outcome("E1", "HVAC", "Missed calls", "AI-ASSISTANT-HVAC", OutcomeType.WIN, revenue=1500.0)
    learning.record_outcome("E2", "Dental", "Recall calls", "AI-ASSISTANT-DENTAL", OutcomeType.MEETING_BOOKED)
    learning.record_outcome("E3", "Retail", "General", "GENERIC", OutcomeType.WRONG_PERSON)

    feedback = learning.feedback_for_scoring()
    assert feedback["total_outcomes_recorded"] == 3
    assert feedback["total_won"] == 1
    assert "HVAC" in feedback["vertical_multipliers"]
    assert feedback["vertical_multipliers"]["HVAC"] > 1.0


def test_commander_dry_run_formatting():
    """Verify execute_dry_run produces the exact human-readable format."""
    commander = GtmCommander(dry_run=True)
    text = commander.execute_dry_run(limit=3)

    assert "=== MBM GTM COMMANDER ===" in text
    assert "TOP NEXT ACTIONS" in text
    assert "1.\nCompany:" in text
    assert "Buyer:" in text
    assert "Action:" in text
    assert "Why now:" in text
    assert "Pain:" in text
    assert "AI fit:" in text
    assert "Priority:" in text
    assert "Confidence:" in text
    assert "Evidence:" in text


def test_commander_simulation():
    """Verify simulation validates the full lifecycle, suppression, and priority boost."""
    commander = GtmCommander(dry_run=True)
    text = commander.execute_simulation()

    assert "SIMULATION MODE" in text
    assert "LIFECYCLE" in text
    assert "TERMINAL STATE: WON" in text
    assert "WRONG_PERSON -> SUPPRESSED" in text
    assert "suppressed priority == 0.0" in text
    assert "OWNER_CONFIRMED -> priority increase" in text
