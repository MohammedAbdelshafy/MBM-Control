"""
TESTS: GTM EXECUTION QUEUE & PRODUCTION RUNNER
=============================================================================
Hermetic unit tests verifying:
1. Top-25 execution queue composition and quality filtering
2. Action packet generation (Phone, Email, LinkedIn)
3. Controlled production runner execution on Top-10 batch
4. Auto-generation of meeting briefs on MEETING_BOOKED
5. Conversion funnel computation and revenue integrity (Proposal != Realized)
=============================================================================
"""

import sys
import json
import pytest
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.gtm_execution_queue import GtmExecutionQueueBuilder, QUEUE_JSON_PATH, QUEUE_MD_PATH
from MBM.LeadEngine.gtm_production_runner import GtmProductionRunner, PROD_REPORT_PATH, METRICS_JSON_PATH
from MBM.LeadEngine.gtm.production_gate import ProductionGate


def test_execution_queue_builder():
    """Verify Top-25 queue builder forms complete records with action packets."""
    builder = GtmExecutionQueueBuilder()
    queue = builder.build_queue(limit=25)

    assert isinstance(queue, list)
    assert len(queue) > 0

    top_item = queue[0]
    required_keys = [
        "rank", "id", "company", "decision_maker", "role", "industry",
        "intent_score", "intent_tier", "pain", "why_now", "recommended_ai_assistant",
        "sku", "monthly_retainer_usd", "ROI_hypothesis", "recommended_channel",
        "priority", "confidence", "evidence", "contactability", "identity_state",
        "suppression_state", "previous_attempts", "next_action", "gate_status", "action_packets"
    ]
    for k in required_keys:
        assert k in top_item, f"Missing key {k} in queue item"

    # Verify action packets
    packets = top_item["action_packets"]
    assert "phone" in packets
    assert "email" in packets
    assert "linkedin" in packets
    assert "opening" in packets["phone"]
    assert "subject" in packets["email"]
    assert "conversation_starter" in packets["linkedin"]


def test_export_queue_artifacts():
    """Verify export_artifacts writes valid JSON and Markdown files."""
    builder = GtmExecutionQueueBuilder()
    md_path = builder.export_artifacts(limit=25)

    assert md_path.exists()
    assert QUEUE_JSON_PATH.exists()

    md_content = md_path.read_text(encoding="utf-8")
    assert "# MBM GTM Top-" in md_content
    assert "Production Gate Status:" in md_content
    assert "Action Packet" in md_content


def test_controlled_production_runner_top10_batch(tmp_path, monkeypatch):
    """Verify execution of Top-10 batch and ZERO-SIMULATION funnel metrics."""
    # Hermetic event store: funnel metrics must be computed from events this
    # test controls, never from production state.
    from MBM.LeadEngine import outreach_event as oe
    isolated_store = tmp_path / "outreach_events.jsonl"
    monkeypatch.setattr(oe, "STORE", isolated_store)

    runner = GtmProductionRunner()
    metrics = runner.run_production_batch(batch_size=10, auto_approve=True)

    assert "funnel" in metrics
    assert "conversion_rates" in metrics
    assert "revenue" in metrics
    assert metrics["metric_source"] == "canonical_outreach_events (zero-simulation)"
    assert metrics["funnel"]["approved"] == 10

    # ZERO-SIMULATION LAW: commercial outcomes exist ONLY with canonical event
    # evidence. An isolated run has no real appointments/payments by definition.
    assert metrics["funnel"]["meetings_booked"] == 0
    assert metrics["funnel"]["deals_won"] == 0
    assert metrics["revenue"]["confirmed_realized_usd"] == 0.0
    # Pipeline claims require payment evidence (no invented pipeline value).
    assert metrics["revenue"]["pipeline_value_usd"] == 0.0

    # Verify report written to disk
    assert PROD_REPORT_PATH.exists()
    assert METRICS_JSON_PATH.exists()


def test_meeting_brief_generation():
    """Verify meeting brief generates clean markdown with Neteller payment link."""
    runner = GtmProductionRunner()
    mock_opp = {
        "company": "Apex Mechanical & Air Solutions",
        "decision_maker": "Marcus Vance",
        "role": "Founder & Managing Director",
        "industry": "HVAC & Mechanical Contractors",
        "contactability": {"phone": "+12148849120", "email": "marcus@apex.com"},
        "intent_score": 100,
        "intent_tier": "HOT",
        "pain": "20+ missed after-hours emergency calls weekly",
        "why_now": "Active hiring for weekend dispatcher",
        "ROI_hypothesis": "Recovers $45,000-$80,000/mo in lost calls",
        "recommended_ai_assistant": "24/7 AI Emergency Call Answering & Dispatch Concierge",
        "sku": "AI-ASSISTANT-HVAC-DISPATCH",
        "monthly_retainer_usd": 1500.0,
        "evidence": {"claim": "Marcus Vance seeks ServiceTitan AI dispatch"},
    }

    brief_path = runner.generate_meeting_brief(mock_opp)
    assert brief_path.exists()
    content = brief_path.read_text(encoding="utf-8")
    assert "# Executive Discovery & Meeting Brief: Apex Mechanical & Air Solutions" in content
    assert "Marcus Vance" in content
    assert "member.neteller.com/pay" in content
    assert "abdelshafyclapps%40gmail.com" in content
    assert "4599228811" in content
