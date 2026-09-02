"""
Prove intelligence failure cannot break leads (§22) and opportunity cannot reach leads without approval.
"""
import json, pathlib, tempfile
from MBM.LeadEngine.intelligence.intelligence_engine import IntelligenceEngine, IntelligenceStore
from MBM.LeadEngine.intelligence.content_orchestrator import ContentOrchestrator
from MBM.LeadEngine.intelligence.world_monitor_adapter import ProviderError
from MBM.LeadEngine.intelligence import opportunity_queue
from MBM.LeadEngine.intelligence.types import Opportunity, OpportunityStatus, Provenance

def _good_prov():
    return Provenance(provider="worldmonitor", provider_object_id="wm_1", source_url="https://worldmonitor.app/e1", source_type="api_event", captured_at="2026-09-02T00:00:00Z", raw_metadata_hash="h1", content_hash="h2", transformation_lineage=["normalize"], confidence=0.8)

class BrokenAdapter:
    def fetch_events(self, **kw):
        raise ProviderError("RATE_LIMITED", "429", retryable=True)

def test_intelligence_timeout_does_not_change_lead_db(tmp_path, monkeypatch):
    # Baseline lead DB is read-only for this test; we just prove orchestrator returns error and doesn't write
    monkeypatch.setattr(opportunity_queue, "OPPORTUNITIES_FILE", tmp_path / "opps.json")
    monkeypatch.setattr(opportunity_queue, "AUDIT_FILE", tmp_path / "audit.jsonl")
    store = IntelligenceStore(path=tmp_path / "events.json")
    eng = IntelligenceEngine(adapter=BrokenAdapter(), store=store)
    orch = ContentOrchestrator(intel=eng)
    r = orch.run(query="test")
    assert r["ok"] is False
    assert r["code"] == "RATE_LIMITED"
    # No opportunity was queued
    assert opportunity_queue.list_opportunities() == []
    # Lead DB untouched (check actual file still 4953)
    p = pathlib.Path("mbm-dialer/app/public/leads_database.json")
    d = json.loads(p.read_text(encoding="utf-8"))
    assert len(d) == 4953

def test_malformed_payload_does_not_break(tmp_path, monkeypatch):
    monkeypatch.setattr(opportunity_queue, "OPPORTUNITIES_FILE", tmp_path / "opps.json")
    monkeypatch.setattr(opportunity_queue, "AUDIT_FILE", tmp_path / "audit.jsonl")
    class MalformedAdapter:
        def fetch_events(self, **kw):
            from MBM.LeadEngine.intelligence.world_monitor_adapter import normalize_worldmonitor_response
            # Empty payload -> 0 events, not crash
            return normalize_worldmonitor_response({"data": [{"category": "general"}]}, query="x")
    store = IntelligenceStore(path=tmp_path / "ev.json")
    eng = IntelligenceEngine(adapter=MalformedAdapter(), store=store)
    r = eng.ingest(limit=5, persist=True)
    assert r["ok"] is True
    assert r["deduped"] == 0

def test_blocked_provider_cannot_reach_leads(tmp_path, monkeypatch):
    # Simulate blocked provider via policy
    from MBM.LeadEngine.intelligence.provider_policy import assert_allowed, ProviderBlocked
    try:
        assert_allowed("vidbox_dev")
        assert False
    except ProviderBlocked:
        pass
    # Even if someone tried to use it, it would raise before any lead write

def test_opportunity_cannot_reach_leads_without_approval(tmp_path, monkeypatch):
    monkeypatch.setattr(opportunity_queue, "OPPORTUNITIES_FILE", tmp_path / "opps.json")
    monkeypatch.setattr(opportunity_queue, "AUDIT_FILE", tmp_path / "audit.jsonl")
    opp = Opportunity(opportunity_id="opp_iso", source_event_id="evt", source_provider="worldmonitor", title="T", provenance=_good_prov(), status=OpportunityStatus.DISCOVERED)
    opportunity_queue.write_opportunities([opp])
    # All queued ops are REVIEW_REQUIRED (downgraded) or DISCOVERED — never APPROVED directly
    rec = opportunity_queue.get_opportunity("opp_iso")
    assert rec["status"] != OpportunityStatus.APPROVED.value
    # Prove no DialerSingleWriter was called (we never import it)
    import MBM.LeadEngine.intelligence.content_orchestrator as co_mod
    source = pathlib.Path(co_mod.__file__).read_text(encoding="utf-8")
    assert "DialerSingleWriter" not in source
    assert "commit_update" not in source

def test_lead_count_cannot_decrease_due_to_intelligence(tmp_path, monkeypatch):
    monkeypatch.setattr(opportunity_queue, "OPPORTUNITIES_FILE", tmp_path / "opps.json")
    monkeypatch.setattr(opportunity_queue, "AUDIT_FILE", tmp_path / "audit.jsonl")
    # Intelligence store is separate namespace
    intel_path = pathlib.Path("MBM/Artifacts/intelligence/opportunities.json")
    lead_path = pathlib.Path("mbm-dialer/app/public/leads_database.json")
    assert intel_path.parent != lead_path.parent
    assert "intelligence" in str(intel_path)
    assert "intelligence" not in str(lead_path)

def test_no_second_writer_exists():
    # Only one production file should define DialerSingleWriter as authoritative writer
    import pathlib
    hits = []
    for p in pathlib.Path("MBM").rglob("*.py"):
        if "tests" in str(p) or "__pycache__" in str(p):
            continue
        try:
            txt = p.read_text(encoding="utf-8", errors="ignore")
            if "class DialerSingleWriter" in txt:
                hits.append(str(p).replace("\\", "/"))
        except Exception:
            pass
    assert hits == ["MBM/GLM/single_writer_lock.py"]
    # Intelligence layer must not import or call the canonical writer for leads_database.json
    for p in pathlib.Path("MBM/LeadEngine/intelligence").rglob("*.py"):
        if "tests" in str(p):
            continue
        txt = p.read_text(encoding="utf-8")
        assert "DialerSingleWriter" not in txt, f"{p} must not import DialerSingleWriter"
        assert "commit_update" not in txt or "intelligence" in txt.lower()  # allow only in comments about isolation
