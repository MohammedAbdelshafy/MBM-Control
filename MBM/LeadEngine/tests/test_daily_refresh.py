#!/usr/bin/env python3
"""
Tests for the MBM LeadEngine daily refresh system.
"""

import json
import tempfile
import os
import sys
from pathlib import Path
from datetime import datetime, timezone, timedelta

# Add repo root to path
ROOT_DIR = Path(__file__).resolve().parents[3]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

# Test the core processing functions
def test_classify_comment():
    """Test comment classification logic."""
    from MBM.LeadEngine.daily_refresh import classify_comment
    
    # Test bad number detection
    assert classify_comment("bad number")["classification"] == "BAD_NUMBER"
    assert classify_comment("wrong number")["classification"] == "BAD_NUMBER"
    assert classify_comment("disconnected")["classification"] == "BAD_NUMBER"
    assert classify_comment("not working")["classification"] == "BAD_NUMBER"
    assert classify_comment("doesn't work")["classification"] == "BAD_NUMBER"
    assert classify_comment("wrong person")["classification"] == "WRONG_PERSON"
    assert classify_comment("tenant")["classification"] == "BAD_NUMBER"
    assert classify_comment("relative")["classification"] == "BAD_NUMBER"
    
    # Test DNC detection
    assert classify_comment("DNC")["classification"] == "DNC"
    assert classify_comment("do not call")["classification"] == "DNC"
    assert classify_comment("don't call")["classification"] == "DNC"
    
    # Test callback detection
    assert classify_comment("call back tomorrow")["classification"] == "CALLBACK"
    assert classify_comment("follow up")["classification"] == "CALLBACK"
    assert classify_comment("scheduled for later")["classification"] == "CALLBACK"
    
    # Test hot detection
    assert classify_comment("hot lead")["classification"] == "HOT"
    assert classify_comment("interested")["classification"] == "HOT"
    assert classify_comment("sounds great")["classification"] == "HOT"
    
    # Test not interested
    assert classify_comment("not interested")["classification"] == "NOT_INTERESTED"
    assert classify_comment("sold")["classification"] == "SOLD"
    
    # Test none
    assert classify_comment("")["classification"] == "NONE"
    assert classify_comment("nice weather today")["classification"] == "NONE"


def test_suppression_functions():
    """Test suppression index functions."""
    from MBM.LeadEngine.daily_refresh import _norm_phone, load_suppression_index
    
    # Test phone normalization
    assert _norm_phone("+1 (210) 555-1234") == "2105551234"
    assert _norm_phone("210-555-1234") == "2105551234"
    assert _norm_phone("2105551234") == "2105551234"
    
    # Test suppression index loading (should not crash)
    suppression_set = load_suppression_index()
    assert isinstance(suppression_set, set)


def test_daily_refresh_dry_run():
    """Test daily refresh in dry-run mode (no actual writes)."""
    # Create temporary copies of all required files
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        
        # Create temp directory structure
        mbm_dir = tmpdir / "MBM"
        leadengine_dir = mbm_dir / "LeadEngine"
        artifacts_dir = mbm_dir / "Artifacts"
        logs_dir = leadengine_dir / "logs"
        public_dir = tmpdir / "mbm-dialer" / "app" / "public"
        
        leadengine_dir.mkdir(parents=True)
        artifacts_dir.mkdir()
        logs_dir.mkdir(parents=True)
        public_dir.mkdir(parents=True)
        
        # Create minimal test files
        # leads_database.json
        test_leads = [
            {
                "id": "TEST-001",
                "company": "Test Company",
                "contact": "John Doe",
                "phone": "+12105550001",
                "vertical": "Test Vertical",
                "motivation_score": 80,
                "deal_score": 70,
                "callability_score": 90,
                "intent_score": 75,
                "discovered_at": datetime.now(timezone.utc).isoformat(),
                "imported_at": datetime.now(timezone.utc).isoformat(),
                "attempts": 0,
                "disposition": "",
                "outcome": "",
            },
            {
                "id": "TEST-002",
                "company": "Another Test",
                "contact": "Jane Smith",
                "phone": "+12105550002",
                "vertical": "Test Vertical",
                "motivation_score": 60,
                "deal_score": 50,
                "callability_score": 85,
                "intent_score": 65,
                "discovered_at": (datetime.now(timezone.utc) - timedelta(days=45)).isoformat(),  # Old
                "imported_at": (datetime.now(timezone.utc) - timedelta(days=45)).isoformat(),
                "attempts": 0,
                "disposition": "",
                "outcome": "",
            }
        ]
        (public_dir / "leads_database.json").write_text(
            json.dumps(test_leads, indent=2), encoding="utf-8"
        )
        
        # disposition logs (empty)
        (logs_dir / "close_dispositions.json").write_text("[]", encoding="utf-8")
        (logs_dir / "call_dispositions.json").write_text("[]", encoding="utf-8")
        
        # comments file (empty)
        (leadengine_dir / "dialer_comments.json").write_text("[]", encoding="utf-8")
        
        # suppression index
        (artifacts_dir / "suppressed_bad_phones.json").write_text(
            json.dumps({
                "total_suppressed_phones": 0,
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "suppressed_phones": []
            }), encoding="utf-8"
        )
        
        # quarantine file
        (artifacts_dir / "quarantined_bad_leads.json").write_text(
            json.dumps({
                "total_quarantined": 0,
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "quarantined_leads": []
            }), encoding="utf-8"
        )
        
        # Change to temp directory and run dry-run
        old_cwd = os.getcwd()
        os.chdir(tmpdir)
        try:
            # Patch module-level constants so the daily refresh uses temp paths
            import MBM.LeadEngine.daily_refresh as dr_mod
            original = {
                "DIALER_DB": dr_mod.DIALER_DB,
                "CLOSE_DISPOSITIONS": dr_mod.CLOSE_DISPOSITIONS,
                "CALL_DISPOSITIONS": dr_mod.CALL_DISPOSITIONS,
                "COMMENTS_FILE": dr_mod.COMMENTS_FILE,
                "SUPPRESSION_FILE": dr_mod.SUPPRESSION_FILE,
                "QUARANTINE_FILE": dr_mod.QUARANTINE_FILE,
            }
            dr_mod.DIALER_DB = public_dir / "leads_database.json"
            dr_mod.CLOSE_DISPOSITIONS = logs_dir / "close_dispositions.json"
            dr_mod.CALL_DISPOSITIONS = logs_dir / "call_dispositions.json"
            dr_mod.COMMENTS_FILE = leadengine_dir / "dialer_comments.json"
            dr_mod.SUPPRESSION_FILE = artifacts_dir / "suppressed_bad_phones.json"
            dr_mod.QUARANTINE_FILE = artifacts_dir / "quarantined_bad_leads.json"

            # Import and run the daily refresh
            import sys
            sys.path.insert(0, str(tmpdir / "MBM" / "LeadEngine"))
            from MBM.LeadEngine.daily_refresh import run_daily_refresh

            result = run_daily_refresh(dry_run=True, quiet=True)

            # Restore
            for k, v in original.items():
                setattr(dr_mod, k, v)

            # Validate results
            assert result["status"] == "dry_run"
            assert result["pre_refresh_count"] == 2
            assert result["post_refresh_count"] == 2
            assert result["top25_gate_pass"] == True
            assert result["metrics"]["new_leads"] >= 0
            assert "top_10" in result
            assert len(result["top_10"]) <= 2  # Only 2 test leads
            
        finally:
            os.chdir(old_cwd)


if __name__ == "__main__":
    test_classify_comment()
    print("✓ test_classify_comment passed")
    
    test_suppression_functions()
    print("✓ test_suppression_functions passed")
    
    test_daily_refresh_dry_run()
    print("✓ test_daily_refresh_dry_run passed")
    
    print("\nAll tests passed!")