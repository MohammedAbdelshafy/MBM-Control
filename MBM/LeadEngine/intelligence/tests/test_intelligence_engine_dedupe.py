import tempfile, pathlib, json
from MBM.LeadEngine.intelligence.intelligence_engine import IntelligenceEngine, IntelligenceStore
from MBM.LeadEngine.intelligence.world_monitor_adapter import WorldMonitorAdapter

class FakeAdapter:
    def __init__(self, payload):
        self._payload = payload
    def fetch_events(self, **kw):
        from MBM.LeadEngine.intelligence.world_monitor_adapter import normalize_worldmonitor_response
        return normalize_worldmonitor_response(self._payload, query=kw.get("query",""))

def test_dedupe_and_store(tmp_path):
    store = IntelligenceStore(path=tmp_path / "events.json")
    payload = {"data": [
        {"title": "Same event", "category": "tech", "publishedAt": "2026-09-01T10:00:00Z"},
        {"title": "Same event", "category": "tech", "publishedAt": "2026-09-01T10:00:00Z"},
        {"title": "Other event", "category": "tech", "publishedAt": "2026-09-01T11:00:00Z"},
    ]}
    eng = IntelligenceEngine(adapter=FakeAdapter(payload), store=store)
    r = eng.ingest(limit=10, persist=True)
    assert r["ok"] is True
    assert r["fetched"] == 3
    assert r["deduped"] == 2
    assert store.count() == 2
    # second ingest same payload should not grow
    r2 = eng.ingest(limit=10, persist=True)
    assert r2["deduped"] == 2
    assert store.count() == 2

def test_failure_does_not_break_caller():
    class BadAdapter:
        def fetch_events(self, **kw):
            from MBM.LeadEngine.intelligence.world_monitor_adapter import ProviderError
            raise ProviderError("RATE_LIMITED", "429", retryable=True)
    store = IntelligenceStore(path=tmp_path / "err.json" if False else pathlib.Path(tempfile.mktemp()))
    eng = IntelligenceEngine(adapter=BadAdapter(), store=store)
    r = eng.ingest(limit=5)
    assert r["ok"] is False
    assert r["code"] == "RATE_LIMITED"
    assert r["events"] == []
