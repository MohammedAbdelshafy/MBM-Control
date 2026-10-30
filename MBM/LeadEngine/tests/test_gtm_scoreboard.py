"""
TESTS: GTM REVENUE SCOREBOARD & SALES LEDGER
=============================================================================
Hermetic tests verifying:
1. GtmSalesLedger event recording, persistence, and retrieval
2. GtmRevenueScoreboard funnel metrics calculation
3. Zero-fabrication enforcement (no revenue without verified transaction)
4. Rate calculations (contact rate, close rate, revenue per attempt)
5. Bottleneck detection across funnel states
6. Integration with GtmCommander
=============================================================================
"""

import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.gtm.scoreboard import GtmSalesLedger, GtmRevenueScoreboard, SPRINT_OFFERS, LANDING_URL
from MBM.LeadEngine.gtm_commander import GtmCommander


def test_sales_ledger_event_recording(tmp_path):
    """Verify recording an atomic sales transition event."""
    ledger_path = tmp_path / "test_ledger.json"
    ledger = GtmSalesLedger(ledger_path=ledger_path)

    event = ledger.record_event(
        prospect_id="PROSPECT-001",
        agent="OUTREACH_AGENT",
        channel="PHONE",
        previous_state="DISCOVERED",
        new_state="CONTACTING",
        action="OUTREACH_CALL_ATTEMPT",
        evidence={"source": "DIALER", "call_id": "call_123"},
        next_action="AWAIT_ANSWER",
        offer="AUDIT",
    )

    assert event["prospect_id"] == "PROSPECT-001"
    assert event["new_state"] == "CONTACTING"
    assert event["offer_price"] == 297.00
    assert "https://whop.com/checkout/plan_e3ibiYXeeAaZV" in event["checkout_url"]
    assert ledger_path.exists()


def test_revenue_scoreboard_metrics_and_zero_fabrication(tmp_path):
    """Verify scoreboard computes rates and enforces zero fake revenue."""
    ledger_path = tmp_path / "test_ledger.json"
    ledger = GtmSalesLedger(ledger_path=ledger_path)

    # 1. Attempt
    ledger.record_event(
        prospect_id="P1",
        agent="OUTREACH",
        channel="PHONE",
        previous_state="DISCOVERED",
        new_state="CONTACTING",
        action="CALL_ATTEMPT",
        evidence={"dialer": True},
        next_action="CONVERSATION",
    )

    # 2. Contact
    ledger.record_event(
        prospect_id="P1",
        agent="CONVERSATION",
        channel="PHONE",
        previous_state="CONTACTING",
        new_state="ENGAGED",
        action="CONTACT_CONNECTED",
        evidence={"duration_sec": 120},
        next_action="QUALIFY",
    )

    # 3. Qualified
    ledger.record_event(
        prospect_id="P1",
        agent="QUALIFIER",
        channel="PHONE",
        previous_state="ENGAGED",
        new_state="QUALIFIED",
        action="QUALIFY_FIT",
        evidence={"pain_verified": True},
        next_action="PRESENT_AUDIT",
    )

    # 4. Checkout Sent
    ledger.record_event(
        prospect_id="P1",
        agent="CLOSER",
        channel="SMS",
        previous_state="QUALIFIED",
        new_state="CHECKOUT_SENT",
        action="SEND_CHECKOUT",
        evidence={"link_clicked": True},
        next_action="AWAIT_PAYMENT",
    )

    scoreboard = GtmRevenueScoreboard(ledger=ledger)
    metrics = scoreboard.compute_metrics(prospects_count=1)

    f = metrics["funnel"]
    r = metrics["rates"]

    assert f["outreach_attempts"] == 1
    assert f["contacts"] == 1
    assert f["conversations"] == 1
    assert f["qualified"] == 1
    assert f["checkout_sent"] == 1
    assert f["purchased"] == 0  # No payment verified yet
    assert f["revenue"] == 0.0

    assert r["contact_rate_pct"] == 100.0
    assert r["conversation_rate_pct"] == 100.0
    assert r["qualification_rate_pct"] == 100.0
    assert r["checkout_rate_pct"] == 100.0
    assert r["close_rate_pct"] == 0.0

    # 5. Add verified purchase
    ledger.record_event(
        prospect_id="P1",
        agent="REVENUE_ANALYST",
        channel="WHOP_WEBHOOK",
        previous_state="CHECKOUT_SENT",
        new_state="PURCHASED",
        action="VERIFY_PAYMENT",
        evidence={"transaction_id": "tx_whop_real_123", "verified_payment": True},
        next_action="ONBOARDING_KICKOFF",
        offer="AUDIT",
        payment_transaction_id="tx_whop_real_123",
        payment_amount_usd=297.00,
        payment_currency="USD",
    )

    metrics2 = scoreboard.compute_metrics(prospects_count=1)
    f2 = metrics2["funnel"]
    assert f2["purchased"] == 1
    assert f2["revenue"] == 297.00
    assert metrics2["rates"]["close_rate_pct"] == 100.0


def test_gtm_commander_scoreboard_export(tmp_path):
    """Verify GtmCommander exports valid scoreboard markdown and JSON."""
    commander = GtmCommander(dry_run=True)
    report_path = commander.export_scoreboard(prospects_count=10)

    assert report_path.exists()
    assert report_path.name == "GTM_REVENUE_SCOREBOARD.md"
    content = report_path.read_text(encoding="utf-8")
    assert "GTM REVENUE SCOREBOARD" in content
    assert "AI Sprint Audit" in content
    assert "https://mbm-dialer-app.vercel.app/sprint/" in content



def test_ledger_persists_acquisition_and_payment_attribution(tmp_path):
    ledger_path = tmp_path / "attribution_ledger.json"
    ledger = GtmSalesLedger(ledger_path=ledger_path)
    event = ledger.record_transition(
        prospect_id="P-ATTR-1",
        agent="HUMAN_OPERATOR",
        channel="PHONE",
        previous_state="DISCOVERED",
        new_state="QUALIFIED",
        action="QUALIFY_FIT",
        evidence={"source": "partner referral"},
        next_action="PREPARE_PROPOSAL",
        lane="HVAC",
        acquisition_channel="PARTNERSHIP",
        vertical_id="hvac",
        campaign_id="fall-hvac-01",
        source_id="partner-west",
        offer_id="hvac-recovery-core",
        offer_type="CORE",
    )

    assert event["channel"] == "PHONE"
    assert event["acquisition_channel"] == "PARTNERSHIP"
    assert event["vertical_id"] == "hvac"
    assert event["campaign_id"] == "fall-hvac-01"
    assert event["source_id"] == "partner-west"
    assert event["offer_id"] == "hvac-recovery-core"
    assert event["offer_type"] == "CORE"

    stored = GtmSalesLedger(ledger_path=ledger_path).get_events()[0]
    assert stored["acquisition_channel"] == "PARTNERSHIP"
    assert stored["offer_type"] == "CORE"


def test_first_touch_attribution_counts_distinct_prospects_and_separates_medium(tmp_path):
    ledger = GtmSalesLedger(ledger_path=tmp_path / "first_touch.json")

    ledger.record_event(
        prospect_id="P1", agent="SOURCE", channel="PHONE",
        previous_state="NEW", new_state="DISCOVERED", action="SOURCE_VERIFIED",
        evidence={"source": "partner"},
        next_action="OUTREACH",
        acquisition_channel="REFERRAL", vertical_id="hvac",
        campaign_id="campaign-referral", source_id="partner-1",
        offer_id="hvac-core", offer_type="CORE",
    )
    ledger.record_event(
        prospect_id="P1", agent="OUTREACH", channel="PHONE",
        previous_state="DISCOVERED", new_state="CONTACTING", action="CALL_ATTEMPT",
        evidence={"call_id": "call-1"}, next_action="QUALIFY",
        acquisition_channel="COLD_OUTREACH",
    )
    ledger.record_event(
        prospect_id="P1", agent="HUMAN", channel="PHONE",
        previous_state="CONTACTING", new_state="ENGAGED", action="CONTACT_CONNECTED",
        evidence={"call_id": "call-1"}, next_action="QUALIFY",
    )
    ledger.record_event(
        prospect_id="P1", agent="HUMAN", channel="PHONE",
        previous_state="ENGAGED", new_state="QUALIFIED", action="QUALIFY_FIT",
        evidence={"pain_confirmed": True}, next_action="BOOK",
    )
    ledger.record_event(
        prospect_id="P1", agent="HUMAN", channel="PHONE",
        previous_state="QUALIFIED", new_state="APPOINTMENT_BOOKED", action="BOOK_APPOINTMENT",
        evidence={"calendar_event_id": "evt-1"}, next_action="DISCOVERY",
    )

    ledger.record_event(
        prospect_id="P2", agent="SOURCE", channel="EMAIL",
        previous_state="NEW", new_state="DISCOVERED", action="SOURCE_VERIFIED",
        evidence={"source": "public directory"}, next_action="OUTREACH",
    )
    ledger.record_event(
        prospect_id="P2", agent="OUTREACH", channel="EMAIL",
        previous_state="DISCOVERED", new_state="EMAIL_SENT", action="OUTREACH_EMAIL_SENT",
        evidence={"message_id": "msg-2", "status": "SENT"}, next_action="AWAIT_REPLY",
    )

    attribution = GtmRevenueScoreboard(ledger=ledger).compute_metrics()["acquisition_attribution"]
    referral = attribution["by_acquisition_channel"]["REFERRAL"]
    unknown = attribution["by_acquisition_channel"]["UNKNOWN"]

    assert referral["prospects_sourced"] == 1
    assert referral["outreach_attempts"] == 1
    assert referral["contacts"] == 1
    assert referral["qualified"] == 1
    assert referral["appointments_booked"] == 1
    assert unknown["prospects_sourced"] == 1
    assert unknown["outreach_attempts"] == 1
    assert attribution["attribution_model"] == "FIRST_TOUCH"
    assert attribution["by_vertical"]["HVAC"]["prospects_sourced"] == 1


def test_verified_payment_needs_explicit_usd_amount_and_transaction_id(tmp_path):
    ledger = GtmSalesLedger(ledger_path=tmp_path / "payment_proof.json")

    paid = dict(
        prospect_id="P-PAID", agent="PAYMENT_WEBHOOK", channel="WEB",
        previous_state="CHECKOUT_SENT", new_state="PURCHASED",
        action="VERIFY_PAYMENT", evidence={"transaction_id": "tx-paid", "verified_payment": True},
        next_action="DELIVER", payment_transaction_id="tx-paid",
        payment_amount_usd=125.00, payment_currency="USD",
    )
    ledger.record_event(**paid)
    ledger.record_event(**paid)  # provider webhook retry must be idempotent
    ledger.record_event(
        prospect_id="P-UNPRICED", agent="PAYMENT_WEBHOOK", channel="WEB",
        previous_state="CHECKOUT_SENT", new_state="PURCHASED",
        action="VERIFY_PAYMENT",
        evidence={"transaction_id": "tx-unpriced", "verified_payment": True},
        next_action="DELIVER", payment_transaction_id="tx-unpriced",
        payment_currency="USD",
    )

    metrics = GtmRevenueScoreboard(ledger=ledger).compute_metrics()
    assert metrics["funnel"]["purchased"] == 2
    assert metrics["funnel"]["revenue"] == 125.00
    assert metrics["acquisition_attribution"]["verified_payment_count"] == 2
    assert metrics["acquisition_attribution"]["unpriced_verified_payments"] == 1
    assert metrics["acquisition_attribution"]["duplicate_payment_events_ignored"] == 1


def test_non_usd_payment_is_not_misreported_as_usd_revenue(tmp_path):
    ledger = GtmSalesLedger(ledger_path=tmp_path / "foreign_currency.json")
    ledger.record_event(
        prospect_id="P-EUR", agent="PAYMENT_WEBHOOK", channel="WEB",
        previous_state="CHECKOUT_SENT", new_state="PURCHASED",
        action="VERIFY_PAYMENT",
        evidence={"transaction_id": "tx-eur", "verified_payment": True},
        next_action="DELIVER", payment_transaction_id="tx-eur",
        payment_currency="EUR",
    )

    metrics = GtmRevenueScoreboard(ledger=ledger).compute_metrics()
    assert metrics["funnel"]["purchased"] == 1
    assert metrics["funnel"]["revenue"] == 0.0
    assert metrics["acquisition_attribution"]["unpriced_verified_payments"] == 1
    assert metrics["acquisition_attribution"]["unsupported_currency_payments"] == 1
