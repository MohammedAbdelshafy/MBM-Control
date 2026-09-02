"""
Critical invariant: failure of intelligence stack must not break lead pipeline.
Orchestrator must fail closed and return structured error, never raise into
caller that would abort daily_lead_ingest / single_writer flows.
"""
import pathlib, tempfile
from MBM.LeadEngine.intelligence.intelligence_engine import IntelligenceEngine, IntelligenceStore
from MBM.LeadEngine.intelligence.content_orchestrator import ContentOrchestrator

class BrokenAdapter:
    def fetch_events(self, **kw):
        from MBM.LeadEngine.intelligence.world_monitor_adapter import ProviderError
        raise ProviderError("RATE_LIMITED", "429", retryable=True)

def test_orchestrator_without_intel_returns_not_configured():
    orch = ContentOrchestrator(intel=None)
    r = orch.run(query="test")
    assert r["ok"] is False
    assert r["code"] == "NOT_CONFIGURED"

def test_orchestrator_propagates_intel_failure_structured():
    store = IntelligenceStore(path=pathlib.Path(tempfile.mktemp(suffix=".json")))
    eng = IntelligenceEngine(adapter=BrokenAdapter(), store=store)
    orch = ContentOrchestrator(intel=eng)
    r = orch.run(query="test", limit=5)
    # orchestrator surfaces the ingest failure as structured error, no exception
    assert r["ok"] is False
    assert r["stage"] == "intelligence"
    assert r["code"] == "RATE_LIMITED"

def test_orchestrator_dry_run_makes_no_external_calls():
    # fake successful ingest but no topview/skysnail wired
    class FakeAdapter:
        def fetch_events(self, **kw):
            from MBM.LeadEngine.intelligence.world_monitor_adapter import normalize_worldmonitor_response
            return normalize_worldmonitor_response({"data": [{"title": "AI for clinics", "category": "tech", "publishedAt": "2026-09-02T10:00:00Z"}]}, query="x")
    store = IntelligenceStore(path=pathlib.Path(tempfile.mktemp(suffix=".json")))
    eng = IntelligenceEngine(adapter=FakeAdapter(), store=store)
    orch = ContentOrchestrator(intel=eng)
    r = orch.run(query="ai clinics", create_drafts=False)
    assert r["ok"] is True
    assert len(r["opportunities"]) >= 1
    assert r["generation_jobs"] == []
    assert r["thumbnail_variants"] == []
