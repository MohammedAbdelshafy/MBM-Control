import tempfile, pathlib, json
from MBM.LeadEngine.intelligence.types import Opportunity, OpportunityStatus, Provenance
from MBM.LeadEngine.intelligence import opportunity_queue

def _good_prov():
    return Provenance(provider="worldmonitor", provider_object_id="wm_1", source_url="https://worldmonitor.app/event/1", source_type="api_event", captured_at="2026-09-02T00:00:00Z", raw_metadata_hash="abc", content_hash="def", transformation_lineage=["normalize"], confidence=0.9)

def _bad_prov():
    return Provenance(provider="worldmonitor", provider_object_id=None, source_url=None, source_type=None, captured_at="2026-09-02T00:00:00Z", raw_metadata_hash=None, content_hash=None, transformation_lineage=[], confidence=None)

def test_valid_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setattr(opportunity_queue, "OPPORTUNITIES_FILE", tmp_path / "opps.json")
    monkeypatch.setattr(opportunity_queue, "AUDIT_FILE", tmp_path / "audit.jsonl")
    opp = Opportunity(opportunity_id="opp_1", source_event_id="evt1", source_provider="worldmonitor", title="Test", summary="S", niche="tech", audience="devs", total_score=0.8, confidence=0.9, provenance=_good_prov(), status=OpportunityStatus.DISCOVERED)
    assert opportunity_queue.write_opportunities([opp]) == 1
    # DISCOVERED -> NORMALIZED
    opportunity_queue.transition_opportunity("opp_1", OpportunityStatus.NORMALIZED, actor="tester", reason="normalize ok")
    # NORMALIZED -> SCORED
    opportunity_queue.transition_opportunity("opp_1", OpportunityStatus.SCORED, actor="tester", reason="score ok")
    # SCORED -> REVIEW_REQUIRED
    opportunity_queue.transition_opportunity("opp_1", OpportunityStatus.REVIEW_REQUIRED, actor="tester", reason="ready review")
    # REVIEW_REQUIRED -> APPROVED (requires good provenance, which we have)
    opportunity_queue.transition_opportunity("opp_1", OpportunityStatus.APPROVED, actor="human@example.com", reason="human approved for test")
    # APPROVED -> CONSUMED
    opportunity_queue.transition_opportunity("opp_1", OpportunityStatus.CONSUMED, actor="human@example.com", reason="consumed after draft lead")
    rec = opportunity_queue.get_opportunity("opp_1")
    assert rec["status"] == OpportunityStatus.CONSUMED.value

def test_invalid_jump_fails_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(opportunity_queue, "OPPORTUNITIES_FILE", tmp_path / "opps.json")
    monkeypatch.setattr(opportunity_queue, "AUDIT_FILE", tmp_path / "audit.jsonl")
    opp = Opportunity(opportunity_id="opp_2", source_event_id="evt2", source_provider="worldmonitor", title="T", provenance=_good_prov(), status=OpportunityStatus.DISCOVERED)
    opportunity_queue.write_opportunities([opp])
    # Cannot jump DISCOVERED -> APPROVED
    try:
        opportunity_queue.transition_opportunity("opp_2", OpportunityStatus.APPROVED, actor="human", reason="try bypass")
        assert False, "should have raised"
    except ValueError as e:
        assert "Invalid transition" in str(e)
    # Cannot jump DISCOVERED -> CONSUMED
    try:
        opportunity_queue.transition_opportunity("opp_2", OpportunityStatus.CONSUMED, actor="human", reason="bypass")
        assert False
    except ValueError:
        pass

def test_provenance_incomplete_forces_review(tmp_path, monkeypatch):
    monkeypatch.setattr(opportunity_queue, "OPPORTUNITIES_FILE", tmp_path / "opps.json")
    monkeypatch.setattr(opportunity_queue, "AUDIT_FILE", tmp_path / "audit.jsonl")
    opp = Opportunity(opportunity_id="opp_3", source_event_id="evt3", source_provider="worldmonitor", title="T", provenance=_bad_prov(), status=OpportunityStatus.DISCOVERED)
    # write should downgrade bad provenance DISCOVERED -> REVIEW_REQUIRED
    opportunity_queue.write_opportunities([opp])
    rec = opportunity_queue.get_opportunity("opp_3")
    assert rec["status"] == OpportunityStatus.REVIEW_REQUIRED.value
    # Cannot approve with bad provenance
    try:
        opportunity_queue.transition_opportunity("opp_3", OpportunityStatus.APPROVED, actor="human", reason="approve bad")
        assert False
    except ValueError as e:
        assert "provenance incomplete" in str(e).lower()

def test_write_never_silently_approves(tmp_path, monkeypatch):
    monkeypatch.setattr(opportunity_queue, "OPPORTUNITIES_FILE", tmp_path / "opps.json")
    monkeypatch.setattr(opportunity_queue, "AUDIT_FILE", tmp_path / "audit.jsonl")
    opp = Opportunity(opportunity_id="opp_4", source_event_id="evt4", source_provider="worldmonitor", title="T", provenance=_good_prov(), status=OpportunityStatus.APPROVED)
    # Direct write with APPROVED should be downgraded to REVIEW_REQUIRED (no silent approve)
    opportunity_queue.write_opportunities([opp])
    rec = opportunity_queue.get_opportunity("opp_4")
    assert rec["status"] == OpportunityStatus.REVIEW_REQUIRED.value
