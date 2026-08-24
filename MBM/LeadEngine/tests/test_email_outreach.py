import pytest
from unittest.mock import patch, MagicMock
import json
import os
import sys
from pathlib import Path

# Add root to sys.path to allow imports
ROOT_DIR = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.email_outreach_engine import EmailOutreachEngine
from MBM.GLM.glm_integration_worker import GLMWorker

@pytest.fixture
def engine():
    return EmailOutreachEngine()

def test_test_fixture_is_blocked(engine):
    lead = {"email": "test@example.com", "source": "TEST_FIXTURE"}
    result = engine.process_and_dispatch_lead(lead)
    assert result["status"] == "blocked"
    assert "TEST_FIXTURE" in result["reason"]

def test_missing_email_is_blocked(engine):
    lead = {"email": "", "company": "Acme"}
    result = engine.process_and_dispatch_lead(lead)
    assert result["status"] == "blocked"

@patch('MBM.LeadEngine.email_outreach_engine.requests.get')
@patch('MBM.LeadEngine.email_outreach_engine.SUPABASE_URL', 'http://mock')
@patch('MBM.LeadEngine.email_outreach_engine.SUPABASE_KEY', 'mock_key')
def test_deduplication_same_campaign_blocked(mock_get, engine):
    # Mocking the Supabase check to return that it found a record
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = [{"id": "123"}]
    mock_get.return_value = mock_response

    lead = {"email": "duplicate@real.com", "campaign": "CAMP_A"}
    result = engine.process_and_dispatch_lead(lead)
    
    assert result["status"] == "blocked"
    assert "already exists for this campaign" in result["reason"]

@patch.object(EmailOutreachEngine, 'is_duplicate')
@patch.object(GLMWorker, 'draft_outreach_email')
def test_model_timeout_handled(mock_draft, mock_duplicate, engine):
    # Mock duplicate check to pass
    mock_duplicate.return_value = False
    
    # Mock draft email to simulate the timeout failure return
    mock_draft.return_value = {
        "body": "Error drafting email: MODEL_UNAVAILABLE (Timeout)", 
        "provider": "Google", 
        "model": "gemini-2.5-flash"
    }

    lead = {"email": "valid@real.com", "company": "MBM Labs"}
    result = engine.process_and_dispatch_lead(lead)

    assert result["status"] == "error"
    assert "MODEL_UNAVAILABLE" in result["reason"]

@patch.object(EmailOutreachEngine, 'is_duplicate')
@patch.object(GLMWorker, 'draft_outreach_email')
@patch.object(GLMWorker, 'qa_outreach_email')
def test_qa_rejection_blocks_dispatch(mock_qa, mock_draft, mock_duplicate, engine):
    mock_duplicate.return_value = False
    mock_draft.return_value = {"body": "Here is my bad email", "provider": "Groq", "model": "llama3"}
    
    # Simulating a malformed JSON failure from QA
    mock_qa.return_value = {"approved": False, "reason": "Malformed JSON: No valid JSON block found in output."}

    lead = {"email": "valid@real.com"}
    result = engine.process_and_dispatch_lead(lead)

    assert result["status"] == "blocked"
    assert "QA Rejected" in result["reason"]
    assert "Malformed JSON" in result["reason"]

@patch.object(EmailOutreachEngine, 'is_duplicate')
@patch.object(GLMWorker, 'draft_outreach_email')
@patch.object(GLMWorker, 'qa_outreach_email')
@patch('MBM.LeadEngine.email_outreach_engine.os.getenv')
def test_gmail_send_flag_disabled(mock_getenv, mock_qa, mock_draft, mock_duplicate, engine):
    # Mock GMAIL_SEND_ENABLED to be false
    def getenv_side_effect(key, default=None):
        if key == "GMAIL_SEND_ENABLED":
            return "false"
        return os.environ.get(key, default)
    mock_getenv.side_effect = getenv_side_effect
    
    # Needs a fresh instance to pick up the mocked env var
    local_engine = EmailOutreachEngine()

    mock_duplicate.return_value = False
    mock_draft.return_value = {"body": "Great email", "provider": "Groq", "model": "llama3"}
    mock_qa.return_value = {"approved": True, "reason": "Looks good"}

    lead = {"email": "valid@real.com", "campaign": "CAMP_A"}
    result = local_engine.process_and_dispatch_lead(lead)

    assert result["status"] == "success_dry_run"
    assert result["record"]["status"] == "qued"


def test_email_normalization(engine):
    # Test that is_test_fixture normalizes and catches mixed-case dummy emails
    assert engine.is_test_fixture({"email": " TEST@example.com "}) is True
    assert engine.is_test_fixture({"email": "abdelshafy@EXAMPle.com"}) is True
    assert engine.is_test_fixture({"email": "valid@realcompany.com"}) is False

