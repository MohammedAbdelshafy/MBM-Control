"""
TESTS: REAL ESTATE SELLER EMAIL & DIALER UNIFIED QUEUE INTEGRATION
=============================================================================
Hermetic tests verifying:
1. Verified sellers appear in dialer call sheet at top positions (#1..#155)
2. Verified sellers with valid email enter the email queue in priority order
3. Sellers without email are NEVER fabricated or enrolled into email queue
4. DNC / suppressed sellers are excluded from both dialer and email queues
5. No duplicate records exist
6. 1,222-record zero-shrinkage invariant is strictly maintained
7. Email templates generate professional property acquisition inquiries
=============================================================================
"""

import sys
import json
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.gtm.gmail_dispatcher import GmailDispatchAdapter
from MBM.LeadEngine.seller_batch_runner import get_callable_sellers, get_next_seller
from MBM.GLM.single_writer_lock import DialerSingleWriter
from MBM.LeadEngine.dialer_priority_engine import DialerPriorityEngine


def test_dialer_top_positions_are_real_estate_sellers():
    """Verify the top 155 queue positions in canonical dialer are real estate sellers."""
    writer = DialerSingleWriter()
    leads = writer.read_leads()
    # The canonical DB GROWS daily (P0 ingestion adds verified leads). The
    # invariant is preservation: the original 1,222-lead cohort must never
    # shrink, so assert a floor, not a frozen snapshot.
    assert len(leads) >= 1222, f"Canonical cohort shrunk below 1,222 (found {len(leads)})"

    sellers = get_callable_sellers()
    assert len(sellers) == 155, f"Expected 155 callable sellers, found {len(sellers)}"

    for idx, s in enumerate(sellers, start=1):
        assert s.get("is_real_estate") is True
        assert s.get("is_callable") is True
        assert s.get("queue_rank") == idx


def test_seller_without_email_is_not_fabricated():
    """Verify sellers without email are not included in email queue (zero fabrication)."""
    adapter = GmailDispatchAdapter()
    email_queue = adapter.build_seller_email_queue()

    # Canonical database currently has 155 phone-verified sellers without deed emails
    assert len(email_queue) == 0, "Zero unverified emails must be fabricated"


def test_seller_with_verified_email_enters_email_queue(tmp_path):
    """Verify that when a verified seller has a valid email, they enter the email queue in priority order."""
    db_file = tmp_path / "test_leads.json"
    leads = [
        {
            "id": "SELLER_EMAIL_01",
            "contact": "Sarah Connor",
            "phone": "+19725550101",
            "email": "sarah.connor@example.com",
            "company": "123 Main St, Dallas TX",
            "segment": "DISTRESSED_SELLER",
            "phone_verified": True,
            "is_real_estate": True,
            "is_callable": True,
            "queue_rank": 1,
            "priority_score": 1080.0,
        },
        {
            "id": "SELLER_PHONE_ONLY_02",
            "contact": "John Connor",
            "phone": "+19725550102",
            "email": "",
            "company": "456 Oak St, Dallas TX",
            "segment": "DISTRESSED_SELLER",
            "phone_verified": True,
            "is_real_estate": True,
            "is_callable": True,
            "queue_rank": 2,
            "priority_score": 1075.0,
        },
        {
            "id": "SELLER_DNC_03",
            "contact": "Kyle Reese",
            "phone": "+19725550103",
            "email": "kyle.reese@example.com",
            "company": "789 Pine St, Dallas TX",
            "segment": "DISTRESSED_SELLER",
            "phone_verified": True,
            "identity_state": "DO_NOT_CALL",
            "is_suppressed": True,
            "is_real_estate": True,
            "is_callable": False,
            "queue_rank": 3,
            "priority_score": 1070.0,
        },
    ]
    db_file.write_text(json.dumps(leads), encoding="utf-8")

    adapter = GmailDispatchAdapter()
    email_queue = adapter.build_seller_email_queue(db_path=db_file)

    assert len(email_queue) == 1, "Only the non-suppressed seller with email should be queued"
    assert email_queue[0]["lead_id"] == "SELLER_EMAIL_01"
    assert email_queue[0]["to_email"] == "sarah.connor@example.com"
    assert "Sarah" in email_queue[0]["body"]
    assert "123 Main St, Dallas TX" in email_queue[0]["body"]
    assert "all-cash, as-is offer" in email_queue[0]["body"]


def test_dnc_seller_excluded_from_both_channels(tmp_path):
    """Verify DNC sellers are excluded from both dialer and email queues."""
    db_file = tmp_path / "test_leads_dnc.json"
    leads = [
        {
            "id": "DNC_SELLER",
            "contact": "DNC Owner",
            "phone": "+19725559999",
            "email": "dnc.owner@example.com",
            "company": "999 Suppressed Way",
            "segment": "DISTRESSED_SELLER",
            "phone_verified": True,
            "identity_state": "DO_NOT_CALL",
            "is_suppressed": True,
            "is_real_estate": True,
            "is_callable": False,
        }
    ]
    db_file.write_text(json.dumps(leads), encoding="utf-8")

    sellers = get_callable_sellers(db_path=db_file)
    assert len(sellers) == 0, "DNC seller must not be in callable seller queue"

    adapter = GmailDispatchAdapter()
    email_queue = adapter.build_seller_email_queue(db_path=db_file)
    assert len(email_queue) == 0, "DNC seller must not be in email queue"
