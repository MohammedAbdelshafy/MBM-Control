from MBM.LeadEngine.intelligence.world_monitor_adapter import normalize_worldmonitor_response

def test_normalizer_envelope_data():
    data = {"data": [{"title": "Fed raises rates", "category": "economy", "publishedAt": "2026-09-01T10:00:00Z"}]}
    events = normalize_worldmonitor_response(data)
    assert len(events) == 1
    assert events[0].title == "Fed raises rates"
    assert events[0].provenance.provider == "worldmonitor"
    assert events[0].freshnessSeconds is not None

def test_normalizer_single_object_wrapped():
    data = {"title": "Quake in TX", "category": "disaster"}
    events = normalize_worldmonitor_response(data)
    assert len(events) == 1

def test_normalizer_drops_untitled():
    data = {"data": [{"category": "general"}]}
    assert normalize_worldmonitor_response(data) == []

def test_normalizer_preserves_provenance_transform():
    data = {"data": [{"title": "Hello", "category": "general"}]}
    e = normalize_worldmonitor_response(data)[0]
    assert e.provenance.transform == "worldMonitorResponse -> IntelligenceEvent[]"

def test_normalizer_topics_and_entities_lists():
    data = {"data": [{"title": "AI deal", "category": "tech", "topics": ["ai", "funding"], "entities": "OpenAI"}]}
    e = normalize_worldmonitor_response(data)[0]
    assert "ai" in e.topics
    assert "OpenAI" in e.entities
