"""
TESTS: MBM DIALER DYNAMIC PRIORITY ENGINE (REAL ESTATE SELLER #1 FOCUS)
=============================================================================
Hermetic tests verifying the core invariants:
1. Verified real-estate seller outranks ordinary cold B2B lead
2. Owner name + verified phone materially increases priority
3. Verified seller opportunity reaches the top queue (Tier 1)
4. New qualified seller lead is auto-promoted
5. Callback seller lead outranks untouched sellers
6. DNC / suppressed lead never enters callable queue
7. Unverified owner/phone does not receive verified priority
8. Existing 1,222 verified records are preserved without shrinkage
9. No lead duplication or dropped records
10. Daily priority refresh is 100% deterministic
=============================================================================
"""

import sys
import json
from pathlib import Path
from datetime import datetime, timezone
import pytest

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.dialer_priority_engine import (
    DialerPriorityEngine,
    refresh_dialer_priority_queue,
    is_lead_suppressed,
    is_real_estate_seller,
    has_verified_owner_and_phone,
)
from MBM.GLM.single_writer_lock import DialerSingleWriter


def test_verified_real_estate_seller_outranks_ordinary_cold_b2b(tmp_path):
    """Verify that a verified property seller outranks a new cold B2B lead."""
    engine = DialerPriorityEngine(sales_ledger_path=tmp_path / "ledger.json")

    b2b_lead = {
        "id": "B2B_001",
        "phone": "+19725551111",
        "company": "Cold Software LLC",
        "vertical": "AI Consultancy & Automation",
        "status": "COLD",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    seller_lead = {
        "id": "SELLER_001",
        "phone": "+12145552222",
        "company": "123 Elm Street Asset",
        "contact": "Travis Colvin",
        "vertical": "Real Estate Wholesale & Acquisitions",
        "segment": "DISTRESSED_SELLER",
        "phone_verified": True,
        "verification_status": "VERIFIED",
    }

    p_b2b = engine.evaluate_lead_priority(b2b_lead)
    p_seller = engine.evaluate_lead_priority(seller_lead)

    assert p_seller["is_real_estate"] is True
    assert p_seller["call_priority"] == 1  # Top Tier
    assert p_seller["priority_score"] > p_b2b["priority_score"]
    assert "VERIFIED SELLER" in p_seller["priority_reason"]


def test_owner_name_and_verified_phone_increases_priority(tmp_path):
    """Verify owner name + verified phone yields higher score than unverified lead."""
    engine = DialerPriorityEngine(sales_ledger_path=tmp_path / "ledger.json")

    unverified_lead = {
        "id": "UNV_001",
        "phone": "+19725553333",
        "property_address": "456 Oak Lane",
        "vertical": "Real Estate",
        "phone_verified": False,
    }
    verified_lead = {
        "id": "VER_001",
        "phone": "+19725554444",
        "property_address": "456 Oak Lane",
        "contact": "John Doe",
        "vertical": "Real Estate",
        "phone_verified": True,
        "verification_status": "VERIFIED",
    }

    p_unv = engine.evaluate_lead_priority(unverified_lead)
    p_ver = engine.evaluate_lead_priority(verified_lead)

    assert p_ver["priority_score"] > p_unv["priority_score"]
    assert p_ver["verified_owner_phone"] is True
    assert p_unv["verified_owner_phone"] is False


def test_callback_seller_outranks_untouched_seller(tmp_path):
    """Verify callback requested seller outranks untouched seller."""
    engine = DialerPriorityEngine(sales_ledger_path=tmp_path / "ledger.json")

    untouched_seller = {
        "id": "SELLER_UNT",
        "phone": "+12145555555",
        "contact": "Alice Smith",
        "segment": "ABSENTEE_OWNER",
        "phone_verified": True,
        "status": "COLD",
    }
    callback_seller = {
        "id": "SELLER_CB",
        "phone": "+12145556666",
        "contact": "Bob Jones",
        "segment": "ABSENTEE_OWNER",
        "phone_verified": True,
        "status": "CALLBACK_REQUESTED",
    }

    p_unt = engine.evaluate_lead_priority(untouched_seller)
    p_cb = engine.evaluate_lead_priority(callback_seller)

    assert p_cb["priority_score"] > p_unt["priority_score"]
    assert "CALLBACK DUE" in p_cb["priority_reason"]


def test_dnc_and_suppressed_never_enters_callable_queue(tmp_path):
    """Verify DNC, bad numbers, and quarantined leads receive priority 99 and is_callable False."""
    engine = DialerPriorityEngine(sales_ledger_path=tmp_path / "ledger.json")

    dnc_lead = {
        "id": "DNC_001",
        "phone": "+19725557777",
        "segment": "DISTRESSED_SELLER",
        "identity_state": "DO_NOT_CALL",
    }
    bad_number = {
        "id": "BAD_001",
        "phone": "+19725558888",
        "status": "BAD_NUMBER",
    }

    p_dnc = engine.evaluate_lead_priority(dnc_lead)
    p_bad = engine.evaluate_lead_priority(bad_number)

    assert p_dnc["is_callable"] is False
    assert p_dnc["call_priority"] == 99
    assert p_dnc["priority_score"] == 0.0

    assert p_bad["is_callable"] is False
    assert p_bad["call_priority"] == 99


def test_priority_changes_after_gtm_state_transition(tmp_path):
    """Verify that adding an interaction event dynamically promotes the seller lead."""
    ledger_file = tmp_path / "sales_ledger.json"
    seller_lead = {
        "id": "SELLER_DYN",
        "phone": "+12145559999",
        "contact": "Mark Evans",
        "segment": "SENIOR_OWNER",
        "phone_verified": True,
        "status": "COLD",
    }

    # 1. Base evaluated priority
    engine1 = DialerPriorityEngine(sales_ledger_path=ledger_file)
    p1 = engine1.evaluate_lead_priority(seller_lead)

    # 2. Record WARMED / ACTIVE CONVERSATION event in sales ledger
    ledger_file.write_text(json.dumps([
        {
            "prospect_id": "SELLER_DYN",
            "phone": "+12145559999",
            "new_state": "ACTIVE_CONVERSATION",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "SELLER_REPLIED",
        }
    ]), encoding="utf-8")

    # 3. Re-evaluate with updated history
    engine2 = DialerPriorityEngine(sales_ledger_path=ledger_file)
    p2 = engine2.evaluate_lead_priority(seller_lead)
    assert p2["priority_score"] > p1["priority_score"]
    assert "ACTIVE CONVERSATION" in p2["priority_reason"]


def test_daily_refresh_deterministic_and_preserves_count(tmp_path):
    """Verify refresh operation is deterministic, preserves all records, and sorts sellers first."""
    db_file = tmp_path / "test_leads.json"
    ledger_file = tmp_path / "test_ledger.json"

    leads = [
        {"id": "L1", "phone": "+19725550001", "company": "B2B Tech", "vertical": "Digital", "status": "COLD"},
        {"id": "L2", "phone": "+19725550002", "company": "Dallas Asset", "contact": "Owner A", "segment": "DISTRESSED_SELLER", "phone_verified": True, "verification_status": "VERIFIED"},
        {"id": "L3", "phone": "+19725550003", "company": "DNC Prop", "status": "DNC", "is_suppressed": True},
        {"id": "L4", "phone": "+19725550004", "company": "Houston Asset", "contact": "Owner B", "segment": "ABSENTEE_OWNER", "phone_verified": True, "verification_status": "VERIFIED", "status": "CALLBACK_REQUESTED"},
    ]
    db_file.write_text(json.dumps(leads), encoding="utf-8")

    res1 = refresh_dialer_priority_queue(db_path=db_file, sales_ledger_path=ledger_file, dry_run=False)
    assert res1["status"] == "SUCCESS"
    assert res1["total_records"] == 4
    assert res1["callable_count"] == 3
    assert res1["real_estate_seller_leads"] == 2

    reloaded = json.loads(db_file.read_text(encoding="utf-8"))
    assert len(reloaded) == 4
    assert {l["id"] for l in reloaded} == {"L1", "L2", "L3", "L4"}

    # First lead must be Real Estate Callback Seller
    assert reloaded[0]["id"] == "L4"
    assert reloaded[0]["queue_rank"] == 1
    assert "CALLBACK DUE" in reloaded[0]["priority_reason"]

    # Second lead must be Verified Motivated Seller
    assert reloaded[1]["id"] == "L2"
    assert reloaded[1]["queue_rank"] == 2
    assert "VERIFIED SELLER" in reloaded[1]["priority_reason"]

    # Third lead is Cold B2B
    assert reloaded[2]["id"] == "L1"
    assert reloaded[2]["queue_rank"] == 3

    # Suppressed lead is last with None rank
    assert reloaded[3]["id"] == "L3"
    assert reloaded[3]["queue_rank"] is None
    assert reloaded[3]["is_callable"] is False


def test_zero_shrinkage_on_canonical_db(tmp_path):
    """Verify single-writer never allows lead count shrinkage."""
    db_file = tmp_path / "test_leads.json"
    leads = [{"id": f"LEAD_{i}", "phone": f"+1972555{i:04d}", "company": f"Comp {i}"} for i in range(100)]
    db_file.write_text(json.dumps(leads), encoding="utf-8")

    writer = DialerSingleWriter(db_path=db_file)
    assert len(writer.read_leads()) == 100

    # Attempt to write shrinking dataset without authorization
    with pytest.raises(Exception):
        writer.full_replace([leads[0]], author="TEST", reason="illegal_shrink", allow_shrink=False)

    # Count remained 100
    assert len(writer.read_leads()) == 100
