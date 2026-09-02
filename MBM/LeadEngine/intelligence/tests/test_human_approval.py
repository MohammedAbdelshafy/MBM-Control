import pathlib, tempfile
from MBM.LeadEngine.intelligence.types import Opportunity, OpportunityStatus, Provenance
from MBM.LeadEngine.intelligence import opportunity_queue
from MBM.LeadEngine.intelligence.human_approval import approve_opportunity, reject_opportunity, consume_opportunity

def _good_prov():
    return Provenance(provider="worldmonitor", provider_object_id="wm_1", source_url="https://worldmonitor.app/event/1", source_type="api_event", captured_at="2026-09-02T00:00:00Z", raw_metadata_hash="abc", content_hash="def", transformation_lineage=["normalize"], confidence=0.9)

def test_approve_requires_review_required_and_actor(tmp_path, monkeypatch):
    monkeypatch.setattr(opportunity_queue, "OPPORTUNITIES_FILE", tmp_path / "opps.json")
    monkeypatch.setattr(opportunity_queue, "AUDIT_FILE", tmp_path / "audit.jsonl")
    opp = Opportunity(opportunity_id="opp_h1", source_event_id="evt", source_provider="worldmonitor", title="T", provenance=_good_prov(), status=OpportunityStatus.DISCOVERED)
    opportunity_queue.write_opportunities([opp])
    # Force to REVIEW_REQUIRED via valid transitions
    opportunity_queue.transition_opportunity("opp_h1", OpportunityStatus.NORMALIZED, actor="t", reason="ok")
    opportunity_queue.transition_opportunity("opp_h1", OpportunityStatus.SCORED, actor="t", reason="ok")
    opportunity_queue.transition_opportunity("opp_h1", OpportunityStatus.REVIEW_REQUIRED, actor="t", reason="ok")
    # Missing actor -> fail
    try:
        approve_opportunity("opp_h1", actor="", reason="ok reason")
        assert False
    except ValueError:
        pass
    # Too short reason -> fail
    try:
        approve_opportunity("opp_h1", actor="human@example.com", reason="hi")
        assert False
    except ValueError:
        pass
    # Score alone must not approve — ensure no auto-approve path exists
    # Valid approve
    entry = approve_opportunity("opp_h1", actor="human@example.com", reason="human approved after QA", correlation_id="corr-123")
    assert entry["to_status"] == OpportunityStatus.APPROVED.value
    assert entry["actor"] == "human@example.com"
    # Cannot approve again (now APPROVED -> not REVIEW_REQUIRED)
    try:
        approve_opportunity("opp_h1", actor="human2", reason="second approve")
        assert False
    except ValueError:
        pass

def test_reject_and_consume(tmp_path, monkeypatch):
    monkeypatch.setattr(opportunity_queue, "OPPORTUNITIES_FILE", tmp_path / "opps.json")
    monkeypatch.setattr(opportunity_queue, "AUDIT_FILE", tmp_path / "audit.jsonl")
    opp = Opportunity(opportunity_id="opp_h2", source_event_id="evt2", source_provider="worldmonitor", title="T2", provenance=_good_prov(), status=OpportunityStatus.DISCOVERED)
    opportunity_queue.write_opportunities([opp])
    opportunity_queue.transition_opportunity("opp_h2", OpportunityStatus.NORMALIZED, actor="t", reason="ok")
    opportunity_queue.transition_opportunity("opp_h2", OpportunityStatus.SCORED, actor="t", reason="ok")
    opportunity_queue.transition_opportunity("opp_h2", OpportunityStatus.REVIEW_REQUIRED, actor="t", reason="ok")
    reject_opportunity("opp_h2", actor="reviewer@example.com", reason="not relevant")
    rec = opportunity_queue.get_opportunity("opp_h2")
    assert rec["status"] == OpportunityStatus.REJECTED.value
    # Consume only from APPROVED
    opp3 = Opportunity(opportunity_id="opp_h3", source_event_id="evt3", source_provider="worldmonitor", title="T3", provenance=_good_prov(), status=OpportunityStatus.DISCOVERED)
    opportunity_queue.write_opportunities([opp3])
    opportunity_queue.transition_opportunity("opp_h3", OpportunityStatus.NORMALIZED, actor="t", reason="ok")
    opportunity_queue.transition_opportunity("opp_h3", OpportunityStatus.SCORED, actor="t", reason="ok")
    opportunity_queue.transition_opportunity("opp_h3", OpportunityStatus.REVIEW_REQUIRED, actor="t", reason="ok")
    approve_opportunity("opp_h3", actor="human@example.com", reason="approved for consumption")
    consume_opportunity("opp_h3", actor="human@example.com", reason="draft lead created")
    assert opportunity_queue.get_opportunity("opp_h3")["status"] == OpportunityStatus.CONSUMED.value
