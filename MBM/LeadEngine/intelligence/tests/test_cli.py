import pytest
from unittest.mock import patch
from MBM.LeadEngine.intelligence.opportunity_cli import review_loop
from MBM.LeadEngine.intelligence.types import OpportunityStatus

def test_cli_dry_run_no_mutation(capsys):
    # Mock list_opportunities to return one REVIEW_REQUIRED
    mock_opps = [{
        "opportunity_id": "test_opp_1",
        "status": OpportunityStatus.REVIEW_REQUIRED.value,
        "title": "Test Opp",
        "summary": "Summary",
    }]
    
    with patch("MBM.LeadEngine.intelligence.opportunity_cli.list_opportunities", return_value=mock_opps):
        with patch("MBM.LeadEngine.intelligence.opportunity_cli.approve_opportunity") as mock_approve:
            # Provide 'a' to approve, then a reason
            inputs = ["a", "looks good"]
            def mock_input(prompt=""):
                return inputs.pop(0) if inputs else "q"
                
            with patch("builtins.input", side_effect=mock_input):
                review_loop(actor="test_user", dry_run=True)
                
            # Ensure DB was not mutated
            mock_approve.assert_not_called()
            
    out, err = capsys.readouterr()
    assert "[DRY RUN]" in out
    assert "Would transition opp test_opp_1 to APPROVED" in out

def test_cli_live_approval(capsys):
    mock_opps = [{
        "opportunity_id": "test_opp_2",
        "status": OpportunityStatus.REVIEW_REQUIRED.value,
    }]
    
    with patch("MBM.LeadEngine.intelligence.opportunity_cli.list_opportunities", return_value=mock_opps):
        with patch("MBM.LeadEngine.intelligence.opportunity_cli.approve_opportunity") as mock_approve:
            inputs = ["a", "verified manually"]
            def mock_input(prompt=""):
                return inputs.pop(0) if inputs else "q"
                
            with patch("builtins.input", side_effect=mock_input):
                review_loop(actor="real_user", dry_run=False)
                
            # Ensure DB WAS mutated
            mock_approve.assert_called_once_with("test_opp_2", actor="real_user", reason="verified manually")

def test_cli_live_rejection(capsys):
    mock_opps = [{
        "opportunity_id": "test_opp_3",
        "status": OpportunityStatus.REVIEW_REQUIRED.value,
    }]
    
    with patch("MBM.LeadEngine.intelligence.opportunity_cli.list_opportunities", return_value=mock_opps):
        with patch("MBM.LeadEngine.intelligence.opportunity_cli.reject_opportunity") as mock_reject:
            inputs = ["r", "invalid data"]
            def mock_input(prompt=""):
                return inputs.pop(0) if inputs else "q"
                
            with patch("builtins.input", side_effect=mock_input):
                review_loop(actor="real_user", dry_run=False)
                
            # Ensure DB WAS mutated
            mock_reject.assert_called_once_with("test_opp_3", actor="real_user", reason="invalid data")
