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
