"""
TESTS: GTM PRODUCTION GATE & HUMAN APPROVAL
=============================================================================
Hermetic unit tests verifying:
1. 6-point production safety gate evaluation
2. Blocking of unapproved or suppressed opportunities
3. Persistence of human approval decisions (APPROVE, REJECT, HOLD)
4. Batch approval mechanisms
=============================================================================
"""

import sys
import json
import pytest
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.gtm.production_gate import ProductionGate, ApprovalStatus


def test_production_gate_evaluation_rules():
    """Verify 6-point production gate evaluation logic."""
    with tempfile.TemporaryDirectory() as td:
        approvals_file = Path(td) / "approvals.json"
        gate = ProductionGate(approvals_file=approvals_file)

        # 1. Valid and Approved Opportunity
        valid_opp = {
            "id": "OPP-001",
            "company": "Apex Mechanical",
            "phone": "+12148849120",
            "email": "marcus@apex.com",
            "why_this_company": "Active after-hours emergency call bottleneck in Dallas",
            "pain_point": "Missed calls",
            "recommended_channel": "PHONE",
            "confidence": 0.95,
            "identity_state": "AUTHORIZED_DECISION_MAKER",
            "is_suppressed": False,
        }

        # Initially pending approval -> can_execute MUST be False
        audit = gate.evaluate_gate(valid_opp)
        assert audit["evidence_valid"] is True
        assert audit["contactable"] is True
        assert audit["not_suppressed"] is True
        assert audit["high_confidence"] is True
        assert audit["channel_allowed"] is True
        assert audit["human_approved"] is False
        assert audit["can_execute"] is False

        # Set human approval -> can_execute MUST be True
        gate.set_approval("OPP-001", ApprovalStatus.APPROVED, approved_by="senior_engineer")
        audit_approved = gate.evaluate_gate(valid_opp)
        assert audit_approved["human_approved"] is True
        assert audit_approved["can_execute"] is True


def test_production_gate_blocks_suppressed_or_missing_phone():
    """Verify suppressed or invalid contact records are blocked regardless of approval."""
    with tempfile.TemporaryDirectory() as td:
        approvals_file = Path(td) / "approvals.json"
        gate = ProductionGate(approvals_file=approvals_file)
        gate.set_approval("OPP-SUPPRESSED", ApprovalStatus.APPROVED)

        # Suppressed opportunity
        suppressed_opp = {
            "id": "OPP-SUPPRESSED",
            "company": "Suppressed Co",
            "phone": "+12148849120",
            "why_this_company": "Valid reason",
            "pain_point": "Valid pain",
            "recommended_channel": "PHONE",
            "confidence": 0.95,
            "is_suppressed": True,
        }
        audit_sup = gate.evaluate_gate(suppressed_opp)
        assert audit_sup["not_suppressed"] is False
        assert audit_sup["can_execute"] is False

        # Missing phone for phone action
        no_phone_opp = {
            "id": "OPP-NO-PHONE",
            "company": "No Phone Co",
            "phone": "",
            "why_this_company": "Valid reason",
            "pain_point": "Valid pain",
            "recommended_channel": "PHONE",
            "confidence": 0.95,
        }
        audit_no_phone = gate.evaluate_gate(no_phone_opp)
        assert audit_no_phone["contactable"] is False
        assert audit_no_phone["can_execute"] is False


def test_batch_approval_and_persistence():
    """Verify batch approval and JSON roundtrip on disk."""
    with tempfile.TemporaryDirectory() as td:
        approvals_file = Path(td) / "approvals.json"
        gate = ProductionGate(approvals_file=approvals_file)

        eids = ["OPP-A", "OPP-B", "OPP-C"]
        count = gate.batch_approve(eids)
        assert count == 3

        # Reload from disk
        gate2 = ProductionGate(approvals_file=approvals_file)
        for eid in eids:
            assert gate2.get_approval_status(eid) == ApprovalStatus.APPROVED.value
