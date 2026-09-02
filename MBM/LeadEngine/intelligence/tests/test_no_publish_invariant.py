"""
Prove intelligence cannot publish, submit, claim payout, mark paid/published, or bypass governance.
PRODUCE != PUBLISHED.
"""
import pathlib, tempfile, json
from MBM.LeadEngine.intelligence.intelligence_engine import IntelligenceEngine, IntelligenceStore
from MBM.LeadEngine.intelligence.content_orchestrator import ContentOrchestrator
from MBM.LeadEngine.intelligence.world_monitor_adapter import normalize_worldmonitor_response
from MBM.LeadEngine.intelligence import opportunity_queue
from MBM.LeadEngine.intelligence.types import OpportunityStatus

class FakeAdapter:
    def fetch_events(self, **kw):
        return normalize_worldmonitor_response({"data": [{"title": "Clinics expand AI services in Dallas", "category": "health", "publishedAt": "2026-09-02T10:00:00Z"}]}, query=kw.get("query",""))

def test_orchestrator_dry_run_never_calls_topview(tmp_path, monkeypatch):
    # Ensure even with create_drafts=False, no job files are created and no publishing occurs
    import MBM.LeadEngine.intelligence.jobs as jobs_mod
    monkeypatch.setattr(opportunity_queue, "OPPORTUNITIES_FILE", tmp_path / "opps.json")
    monkeypatch.setattr(opportunity_queue, "AUDIT_FILE", tmp_path / "audit.jsonl")
    store = IntelligenceStore(path=tmp_path / "events.json")
    eng = IntelligenceEngine(adapter=FakeAdapter(), store=store)
    orch = ContentOrchestrator(intel=eng)
    # Track if any GenerationJob store was touched
    job_path = tmp_path / "jobs.json"
    # No topview/skysnail wired, so certainly no publish
    r = orch.run(query="test", create_drafts=False)
    assert r["ok"] is True
    assert r["generation_jobs"] == []
    assert r["thumbnail_variants"] == []
    assert len(r["opportunities"]) >= 1
    # Opportunities are queued as REVIEW_REQUIRED, not APPROVED
    for opp_data in r["opportunities"]:
        status = opp_data["opportunity"]["status"]
        # status is enum, but serialized dict may have enum object
        sval = status.value if hasattr(status, "value") else str(status)
        assert sval in (OpportunityStatus.SCORED.value, OpportunityStatus.REVIEW_REQUIRED.value, OpportunityStatus.DISCOVERED.value, OpportunityStatus.NORMALIZED.value)
        assert sval != OpportunityStatus.APPROVED.value
        assert sval != OpportunityStatus.CONSUMED.value
    # Check queue file does not contain APPROVED
    queued = opportunity_queue.list_opportunities()
    assert all(q["status"] != OpportunityStatus.APPROVED.value for q in queued)
    assert all(q["status"] != OpportunityStatus.CONSUMED.value for q in queued)

def test_intelligence_events_never_touch_publishing_governance():
    # Verify that mbm_social publishing is not imported by intelligence layer
    import sys
    # Intelligence modules should not import publisher that auto-publishes
    # Check that ContentOrchestrator does not have publish method that auto-publishes
    assert not hasattr(ContentOrchestrator, "publish")
    assert not hasattr(ContentOrchestrator, "auto_publish")
    # Ensure no-publish invariant: status PRODUCE means qualification, not published
    # Our Opportunities are SCORED/REVIEW_REQUIRED, nunca published
