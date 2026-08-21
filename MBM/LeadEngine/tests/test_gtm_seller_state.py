"""
TESTS: GTM SELLER STATE INTERPRETER & NEXT-BEST-ACTION
=============================================================================
Hermetic tests verifying:
1. Terminal 1 disposition contract (GtmSalesLedger.record_transition)
2. Zero fabrication: empty ledger -> zero sellers, zero actions
3. State interpretation from REAL recorded events only
4. Exactly ONE next action per seller
5. Commercial priority ordering (conversation > callback > interested > ...)
6. Terminal states (DNC) excluded from active ranking
7. Scoreboard counts cascade/WhatsApp outreach as real seller attempts
8. Revenue only with verified transaction evidence
=============================================================================
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.gtm.scoreboard import GtmSalesLedger, GtmRevenueScoreboard
from MBM.LeadEngine.gtm.seller_state import (
    interpret_seller_events,
    rank_active_sellers,
    seller_pipeline_summary,
    ACTION_CALLBACK,
    ACTION_BOOK_APPOINTMENT,
    ACTION_QUALIFY,
    ACTION_PREPARE_OFFER,
    ACTION_WAIT,
    ACTION_FOLLOW_UP,
)


def _ledger(tmp_path):
    return GtmSalesLedger(ledger_path=tmp_path / "seller_ledger.json")


def test_record_transition_contract(tmp_path):
    """Terminal 1 calls record_transition(...) — the contract must exist and persist."""
    ledger = _ledger(tmp_path)
    event = ledger.record_transition(
        prospect_id="SELLER-001",
        agent="OPERATOR_HUMAN",
        channel="PHONE",
        previous_state="QUEUED",
        new_state="CALLBACK_REQUESTED",
        action="SELLER_CALLBACK_REQUESTED",
        evidence={"disposition": "CALLBACK_REQUESTED", "phone": "+12105550000"},
        next_action="FOLLOW_UP",
        notes="call back tomorrow 10am",
    )
    assert event["prospect_id"] == "SELLER-001"
    assert event["new_state"] == "CALLBACK_REQUESTED"
    reloaded = GtmSalesLedger(ledger_path=ledger.ledger_path)
    assert len(reloaded.get_events()) == 1


def test_empty_ledger_fabricates_nothing(tmp_path):
    ledger = _ledger(tmp_path)
    interpreted = interpret_seller_events(ledger.get_events())
    assert interpreted == {}
    assert rank_active_sellers(interpreted) == []
    metrics = GtmRevenueScoreboard(ledger=ledger).compute_metrics(prospects_count=0)
    assert metrics["real_estate"]["real_estate_seller_leads"] == 0
    assert metrics["funnel"]["outreach_attempts"] == 0


def test_cascade_outreach_counts_as_seller_attempt(tmp_path):
    """Only CONFIRMED sends count as attempts; a generated-but-unsent link does not."""
    ledger = _ledger(tmp_path)
    # Link generated but NOT sent -> seller lead, but NOT an attempt.
    ledger.record_event(
        prospect_id="AI-BUYER-LINK", agent="SELLER_CASCADE_ENGINE",
        channel="WHATSAPP", previous_state="CASCADE_QUEUED",
        new_state="WHATSAPP_LINK_READY",
        action="SELLER_CASCADE_DAY_0_INITIAL",
        evidence={"phone": "+12109945512", "status": "LINK_READY"},
        next_action="FOLLOW_UP",
    )
    # Confirmed send -> real attempt.
    ledger.record_event(
        prospect_id="SELLER-SENT", agent="SELLER_CASCADE_ENGINE",
        channel="WHATSAPP", previous_state="CASCADE_QUEUED",
        new_state="WHATSAPP_SENT",
        action="SELLER_CASCADE_DAY_0_INITIAL",
        evidence={"phone": "+12105550001", "status": "SENT"},
        next_action="WAIT_FOR_RESPONSE",
    )
    metrics = GtmRevenueScoreboard(ledger=ledger).compute_metrics()
    assert metrics["funnel"]["outreach_attempts"] == 1
    assert metrics["real_estate"]["seller_outreach_attempts"] == 1
    assert metrics["real_estate"]["real_estate_seller_leads"] == 2

    interpreted = interpret_seller_events(ledger.get_events())
    ranked = rank_active_sellers(interpreted)
    assert len(ranked) == 2
    by_id = {s["prospect_id"]: s for s in ranked}
    # Link generated but NOT confirmed sent -> WAIT (never presume a send).
    assert by_id["AI-BUYER-LINK"]["next_action"] == ACTION_WAIT
    assert by_id["SELLER-SENT"]["next_action"] == ACTION_WAIT


def test_one_action_per_seller_and_priority_order(tmp_path):
    ledger = _ledger(tmp_path)
    # Seller A: interested (tier 3)
    ledger.record_event(
        prospect_id="A-INTERESTED", agent="OP", channel="PHONE",
        previous_state="CONTACTED", new_state="INTERESTED",
        action="SELLER_INTERESTED", evidence={}, next_action="BOOK",
    )
    # Seller B: callback requested (tier 2 — outranks interested)
    ledger.record_event(
        prospect_id="B-CALLBACK", agent="OP", channel="PHONE",
        previous_state="CONTACTED", new_state="CALLBACK_REQUESTED",
        action="SELLER_CALLBACK_REQUESTED", evidence={}, next_action="CALLBACK",
    )
    # Seller C: active conversation (tier 1 — outranks everything)
    ledger.record_event(
        prospect_id="C-ACTIVE", agent="OP", channel="PHONE",
        previous_state="QUEUED", new_state="CONTACTED",
        action="SELLER_CONTACTED", evidence={}, next_action="QUALIFY",
    )
    # Seller D: qualified (tier 4)
    ledger.record_event(
        prospect_id="D-QUALIFIED", agent="OP", channel="PHONE",
        previous_state="ENGAGED", new_state="QUALIFIED",
        action="SELLER_QUALIFIED", evidence={}, next_action="APPOINTMENT",
    )

    interpreted = interpret_seller_events(ledger.get_events())
    assert len(interpreted) == 4  # exactly one state per seller

    ranked = rank_active_sellers(interpreted)
    ids = [s["prospect_id"] for s in ranked]
    assert ids[0] == "C-ACTIVE"       # active conversation first
    assert ids[1] == "B-CALLBACK"     # callback due second
    assert ids[2] == "A-INTERESTED"   # interested third
    assert ids[3] == "D-QUALIFIED"    # qualified fourth

    actions = {s["prospect_id"]: s["next_action"] for s in ranked}
    assert actions["C-ACTIVE"] == ACTION_QUALIFY
    assert actions["B-CALLBACK"] == ACTION_CALLBACK
    assert actions["A-INTERESTED"] == ACTION_BOOK_APPOINTMENT
    assert actions["D-QUALIFIED"] == ACTION_BOOK_APPOINTMENT


def test_appointment_then_offer_chain(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record_event(
        prospect_id="E-CHAIN", agent="OP", channel="PHONE",
        previous_state="QUALIFIED", new_state="APPOINTMENT_BOOKED",
        action="SELLER_APPOINTMENT", evidence={}, next_action="PREP_OFFER",
    )
    interpreted = interpret_seller_events(ledger.get_events())
    assert interpreted["E-CHAIN"]["next_action"] == ACTION_PREPARE_OFFER

    # Offer made -> offer follow-up
    ledger.record_event(
        prospect_id="E-CHAIN", agent="OP", channel="EMAIL",
        previous_state="APPOINTMENT_BOOKED", new_state="OFFER_MADE",
        action="SELLER_OFFER_MADE", evidence={}, next_action="FOLLOW_UP",
    )
    interpreted = interpret_seller_events(ledger.get_events())
    assert interpreted["E-CHAIN"]["next_action"] == ACTION_FOLLOW_UP
    metrics = GtmRevenueScoreboard(ledger=ledger).compute_metrics()
    assert metrics["real_estate"]["seller_offers"] == 1


def test_dnc_terminal_excluded_from_ranking(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record_event(
        prospect_id="Z-DNC", agent="OP", channel="PHONE",
        previous_state="CONTACTED", new_state="DNC",
        action="SELLER_DNC", evidence={}, next_action="CLOSE",
    )
    interpreted = interpret_seller_events(ledger.get_events())
    assert interpreted["Z-DNC"]["terminal"] is True
    assert interpreted["Z-DNC"]["next_action"] == "DNC"
    assert rank_active_sellers(interpreted) == []


def test_revenue_requires_transaction_evidence(tmp_path):
    ledger = _ledger(tmp_path)
    # Deal WON without transaction evidence -> NO revenue counted.
    ledger.record_event(
        prospect_id="R-NO-EVIDENCE", agent="OP", channel="PHONE",
        previous_state="OFFER_MADE", new_state="DEAL_WON",
        action="SELLER_DEAL_WON", evidence={"verbal_only": True},
        next_action="ONBOARD",
    )
    metrics = GtmRevenueScoreboard(ledger=ledger).compute_metrics()
    assert metrics["funnel"]["purchased"] == 0
    assert metrics["funnel"]["revenue"] == 0.0
    assert metrics["real_estate"]["seller_deals"] == 0

    # With verified transaction evidence -> counted exactly once.
    ledger.record_event(
        prospect_id="R-EVIDENCE", agent="ANALYST", channel="WHOP_WEBHOOK",
        previous_state="OFFER_MADE", new_state="DEAL_WON",
        action="SELLER_DEAL_WON",
        evidence={"transaction_id": "tx_real_9", "verified_payment": True},
        next_action="ONBOARD",
    )
    metrics2 = GtmRevenueScoreboard(ledger=ledger).compute_metrics()
    assert metrics2["funnel"]["purchased"] == 1
    assert metrics2["funnel"]["revenue"] == 297.0
    assert metrics2["real_estate"]["seller_deals"] == 1
    assert metrics2["real_estate"]["seller_revenue"] == 297.0


def test_latest_event_wins_no_duplicate_state(tmp_path):
    ledger = _ledger(tmp_path)
    ledger.record_event(
        prospect_id="M-LATEST", agent="CASCADE", channel="WHATSAPP",
        previous_state="CASCADE_QUEUED", new_state="WHATSAPP_SENT",
        action="SELLER_CASCADE_DAY_0_INITIAL", evidence={}, next_action="WAIT",
    )
    ledger.record_event(
        prospect_id="M-LATEST", agent="OP", channel="PHONE",
        previous_state="WHATSAPP_SENT", new_state="CONTACTED",
        action="SELLER_CONTACTED", evidence={}, next_action="QUALIFY",
    )
    interpreted = interpret_seller_events(ledger.get_events())
    assert len(interpreted) == 1
    assert interpreted["M-LATEST"]["state"] == "CONTACTED"
    summary = seller_pipeline_summary(interpreted)
    assert summary == {"ACTIVE_CONVERSATION": 1}
