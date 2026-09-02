import pytest
import json
from unittest.mock import patch
from pathlib import Path

from MBM.LeadEngine.intelligence.opportunity_queue import _write_all, list_opportunities, get_opportunity, OPPORTUNITIES_FILE, AUDIT_FILE
from MBM.LeadEngine.intelligence.opportunity_cli import review_loop
from MBM.LeadEngine.intelligence.types import OpportunityStatus
from MBM.LeadEngine.intelligence.human_approval import approve_opportunity

@pytest.fixture
def clean_queue():
    if OPPORTUNITIES_FILE.exists():
        OPPORTUNITIES_FILE.unlink()
    if AUDIT_FILE.exists():
        AUDIT_FILE.unlink()
    yield
    if OPPORTUNITIES_FILE.exists():
        OPPORTUNITIES_FILE.unlink()
    if AUDIT_FILE.exists():
        AUDIT_FILE.unlink()

def create_mock_opp(opp_id="opp_123", status=OpportunityStatus.REVIEW_REQUIRED.value):
    return {
        "opportunity_id": opp_id,
        "status": status,
        "title": "Test Opp",
        "provenance": {
            "provider": "test_provider",
            "provider_object_id": opp_id,
            "source_url": "http://test",
            "source_type": "api",
            "captured_at": "2026-01-01T00:00:00Z",
            "raw_metadata_hash": "hash1",
            "content_hash": "hash2",
            "transformation_lineage": ["lineage"],
            "confidence": 0.9,
            "tool": "test",
            "rawReference": "{}"
        }
    }

def test_dry_run_no_write_behavior(clean_queue):
    _write_all([create_mock_opp("opp_dry")])
    
    # Mock inputs: 'a' for approve, then 'test reason'
    inputs = ["a", "test reason", "q"]
    def mock_input(prompt=""):
        return inputs.pop(0)
    
    with patch("builtins.input", mock_input):
        review_loop(actor="test_user", dry_run=True)
        
    opp = get_opportunity("opp_dry")
    # Status should remain REVIEW_REQUIRED because it was a dry run
    assert opp["status"] == OpportunityStatus.REVIEW_REQUIRED.value

def test_fail_closed_on_malformed_json(clean_queue):
    OPPORTUNITIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    OPPORTUNITIES_FILE.write_text("invalid json")
    
    with pytest.raises(ValueError, match="Corruption detected"):
        list_opportunities()

def test_audit_trail_integrity_marker(clean_queue):
    _write_all([create_mock_opp("opp_audit")])
    
    # Actually approve it
    approve_opportunity("opp_audit", actor="test_actor", reason="good opp")
    
    # Check audit log
    audit_lines = AUDIT_FILE.read_text().strip().split("\n")
    last_log = json.loads(audit_lines[-1])
    
    assert last_log["event"] == "opportunity_transition"
    assert last_log["opportunity_id"] == "opp_audit"
    assert last_log["to_status"] == OpportunityStatus.APPROVED.value
    assert last_log["provenance_hash"] == "hash2" # content_hash

def test_actor_requirement(clean_queue):
    _write_all([create_mock_opp("opp_actor")])
    with pytest.raises(ValueError, match="actor is required"):
        approve_opportunity("opp_actor", actor="", reason="reason")

def test_missing_provenance_blocking(clean_queue):
    bad_opp = create_mock_opp("opp_bad")
    del bad_opp["provenance"]["source_url"] # Break provenance
    _write_all([bad_opp])
    
    with pytest.raises(ValueError, match="provenance incomplete"):
        approve_opportunity("opp_bad", actor="test_actor", reason="reason")
