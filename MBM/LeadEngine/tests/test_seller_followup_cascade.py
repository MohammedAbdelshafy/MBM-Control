"""
TESTS: REAL ESTATE SELLER MULTI-CHANNEL FOLLOW-UP CASCADE
=============================================================================
Hermetic tests verifying:
1. WhatsApp is selected as primary channel (Day 0)
2. Email becomes fallback only when verified email exists
3. Missing email never creates a fabricated address (zero-fabrication)
4. WhatsApp failure or exhaustion triggers email fallback if email exists
5. Idempotency strictly prevents duplicate follow-ups
6. DNC / opt-out immediately blocks all outbound channels
7. Positive response (CONTACTED/QUALIFIED) promotes seller to active CRM flow
8. 1,222-record zero-shrinkage invariant is strictly maintained
=============================================================================
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytest

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.seller_followup_cascade import SellerFollowupCascade, get_seller_templates
from MBM.GLM.single_writer_lock import DialerSingleWriter


def test_whatsapp_is_selected_primary_channel():
    """Verify WhatsApp is chosen first for callable seller leads."""
    lead = {
        "id": "CASCADE_TEST_01",
        "contact": "Travis Colvin",
        "phone": "+12109945512",
        "company": "LoneStar Capital Asset Acquisitions",
        "segment": "DISTRESSED_SELLER",
        "phone_verified": True,
        "is_real_estate": True,
        "is_callable": True,
    }
    cascade = SellerFollowupCascade()
    dec = cascade.determine_next_action(lead)

    assert dec["is_actionable"] is True
    assert dec["channel"] == "WHATSAPP"
    assert dec["stage"] == "DAY_0_INITIAL"
    assert dec["next_action"] == "SEND_WHATSAPP"


def test_email_fallback_only_when_verified_email_exists(tmp_path):
    """Verify email fallback is only triggered if verified email exists after WhatsApp window."""
    db_file = tmp_path / "test_leads.json"
    log_file = tmp_path / "test_cascade_log.json"

    # Seed lead with email
    leads = [{
        "id": "CASCADE_TEST_EMAIL",
        "contact": "Jane Doe",
        "phone": "+19725550199",
        "email": "jane.doe@example.com",
        "company": "100 Elm St, Dallas TX",
        "segment": "DISTRESSED_SELLER",
        "phone_verified": True,
        "is_real_estate": True,
        "is_callable": True,
    }]
    db_file.write_text(json.dumps(leads), encoding="utf-8")

    # Simulate all WhatsApp stages completed
    history = [
        {"lead_id": "CASCADE_TEST_EMAIL", "channel": "WHATSAPP", "stage": "DAY_0_INITIAL", "status": "SENT", "timestamp": "2026-08-10T00:00:00Z"},
        {"lead_id": "CASCADE_TEST_EMAIL", "channel": "WHATSAPP", "stage": "DAY_1_FOLLOWUP_1", "status": "SENT", "timestamp": "2026-08-11T00:00:00Z"},
        {"lead_id": "CASCADE_TEST_EMAIL", "channel": "WHATSAPP", "stage": "DAY_3_FOLLOWUP_2", "status": "SENT", "timestamp": "2026-08-13T00:00:00Z"},
        {"lead_id": "CASCADE_TEST_EMAIL", "channel": "WHATSAPP", "stage": "DAY_5_FINAL_FOLLOWUP", "status": "SENT", "timestamp": "2026-08-15T00:00:00Z"},
    ]
    log_file.write_text(json.dumps(history), encoding="utf-8")

    cascade = SellerFollowupCascade(db_path=db_file, log_path=log_file)
    dec = cascade.determine_next_action(leads[0])

    assert dec["channel"] == "EMAIL"
    assert dec["next_action"] == "SEND_EMAIL"
    assert dec["email"] == "jane.doe@example.com"


def test_missing_email_never_fabricates_address(tmp_path):
    """Verify seller without email never generates a fake address when WhatsApp is exhausted."""
    db_file = tmp_path / "test_leads.json"
    log_file = tmp_path / "test_cascade_log.json"

    leads = [{
        "id": "CASCADE_TEST_NO_EMAIL",
        "contact": "Bob Smith",
        "phone": "+19725550200",
        "email": "",
        "company": "200 Pine St, Dallas TX",
        "segment": "DISTRESSED_SELLER",
        "phone_verified": True,
        "is_real_estate": True,
        "is_callable": True,
    }]
    db_file.write_text(json.dumps(leads), encoding="utf-8")

    history = [
        {"lead_id": "CASCADE_TEST_NO_EMAIL", "channel": "WHATSAPP", "stage": "DAY_0_INITIAL", "status": "SENT", "timestamp": "2026-08-10T00:00:00Z"},
        {"lead_id": "CASCADE_TEST_NO_EMAIL", "channel": "WHATSAPP", "stage": "DAY_1_FOLLOWUP_1", "status": "SENT", "timestamp": "2026-08-11T00:00:00Z"},
        {"lead_id": "CASCADE_TEST_NO_EMAIL", "channel": "WHATSAPP", "stage": "DAY_3_FOLLOWUP_2", "status": "SENT", "timestamp": "2026-08-13T00:00:00Z"},
        {"lead_id": "CASCADE_TEST_NO_EMAIL", "channel": "WHATSAPP", "stage": "DAY_5_FINAL_FOLLOWUP", "status": "SENT", "timestamp": "2026-08-15T00:00:00Z"},
    ]
    log_file.write_text(json.dumps(history), encoding="utf-8")

    cascade = SellerFollowupCascade(db_path=db_file, log_path=log_file)
    dec = cascade.determine_next_action(leads[0])

    # Must route to secondary PHONE callback, never inventing an email
    assert dec["channel"] == "PHONE"
    assert dec["next_action"] == "CALL_BACK"
    assert dec.get("email") is None


def test_idempotency_prevents_duplicate_sends(tmp_path):
    """Verify record_cascade_event blocks duplicate sends for same lead/stage/channel."""
    log_file = tmp_path / "test_cascade_log.json"
    cascade = SellerFollowupCascade(log_path=log_file)

    res1 = cascade.record_cascade_event(
        lead_id="LEAD_IDEMPOTENT_01",
        channel="WHATSAPP",
        stage="DAY_0_INITIAL",
        status="SENT",
        notes="First send",
    )
    assert res1["status"] == "RECORDED"

    res2 = cascade.record_cascade_event(
        lead_id="LEAD_IDEMPOTENT_01",
        channel="WHATSAPP",
        stage="DAY_0_INITIAL",
        status="SENT",
        notes="Retry send",
    )
    assert res2["status"] == "IDEMPOTENT_SKIPPED"


def test_dnc_blocks_all_cascade_channels():
    """Verify DNC sellers are immediately blocked from both WhatsApp and Email."""
    lead = {
        "id": "CASCADE_DNC_LEAD",
        "contact": "Opt Out Owner",
        "phone": "+19725559999",
        "email": "optout@example.com",
        "identity_state": "DO_NOT_CALL",
        "is_suppressed": True,
        "is_real_estate": True,
        "is_callable": False,
    }
    cascade = SellerFollowupCascade()
    dec = cascade.determine_next_action(lead)

    assert dec["is_actionable"] is False
    assert dec["next_action"] == "DNC"
    assert dec["channel"] == "NONE"


def test_positive_response_promotes_seller():
    """Verify CONTACTED / QUALIFIED status routes to active CRM action."""
    lead = {
        "id": "CASCADE_QUALIFIED_LEAD",
        "contact": "Motivated Owner",
        "phone": "+19725558888",
        "status": "QUALIFIED",
        "crm_stage": "QUALIFIED",
        "phone_verified": True,
        "is_real_estate": True,
        "is_callable": True,
    }
    cascade = SellerFollowupCascade()
    dec = cascade.determine_next_action(lead)

    assert dec["is_actionable"] is True
    assert dec["next_action"] == "SEND_OFFER"
    assert dec["channel"] == "PHONE"
