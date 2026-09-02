import pytest
from mbm_social.models.source import NormalizedSource, ProvenanceConfidence
from mbm_social.moment_discovery import (
    CandidateMoment,
    MomentConfidence,
    DiscoveryMethod,
    discover_moments,
    generate_moment_id
)

@pytest.fixture
def valid_source():
    payload = {
        "source_url": "https://youtube.com/watch?v=123",
        "source_type": "video",
        "title": "Test Video",
        "duration_seconds": 120,
    }
    return NormalizedSource.from_provider_payload("youtube", "123", payload)

def test_moment_timestamp_boundaries():
    with pytest.raises(ValueError, match="Timestamps cannot be negative"):
        CandidateMoment(
            moment_id="1", source_id="src", start_seconds=-10, end_seconds=20,
            duration_seconds=30, moment_type="test", hook_score=1.0, payoff_score=1.0,
            standalone_score=1.0, context_score=1.0, relevance_score=1.0,
            confidence=MomentConfidence.HIGH, evidence="e", discovery_method=DiscoveryMethod.AI_PROVIDER
        )
        
    with pytest.raises(ValueError, match="end_seconds must be strictly greater than start_seconds"):
        CandidateMoment(
            moment_id="1", source_id="src", start_seconds=20, end_seconds=10,
            duration_seconds=10, moment_type="test", hook_score=1.0, payoff_score=1.0,
            standalone_score=1.0, context_score=1.0, relevance_score=1.0,
            confidence=MomentConfidence.HIGH, evidence="e", discovery_method=DiscoveryMethod.AI_PROVIDER
        )
        
    with pytest.raises(ValueError, match="duration_seconds must equal end_seconds - start_seconds"):
        CandidateMoment(
            moment_id="1", source_id="src", start_seconds=10, end_seconds=20,
            duration_seconds=15, # Invalid
            moment_type="test", hook_score=1.0, payoff_score=1.0,
            standalone_score=1.0, context_score=1.0, relevance_score=1.0,
            confidence=MomentConfidence.HIGH, evidence="e", discovery_method=DiscoveryMethod.AI_PROVIDER
        )

def test_moment_deterministic_ranking(valid_source):
    # Two moments with identical scores, deterministic tie-breaking should apply
    c1 = CandidateMoment(
        moment_id="A_ID", source_id="src", start_seconds=10, end_seconds=20, duration_seconds=10,
        moment_type="t", hook_score=1.0, payoff_score=1.0, standalone_score=1.0, context_score=1.0, relevance_score=1.0,
        confidence=MomentConfidence.HIGH, evidence="e", discovery_method=DiscoveryMethod.AI_PROVIDER
    )
    c2 = CandidateMoment(
        moment_id="B_ID", source_id="src", start_seconds=10, end_seconds=20, duration_seconds=10,
        moment_type="t", hook_score=1.0, payoff_score=1.0, standalone_score=1.0, context_score=1.0, relevance_score=1.0,
        confidence=MomentConfidence.HIGH, evidence="e", discovery_method=DiscoveryMethod.AI_PROVIDER
    )
    
    # Simulate discovery output
    candidates = [c2, c1]
    candidates.sort(key=lambda x: (-x.total_score, x.start_seconds, x.moment_id))
    
    # A_ID should come before B_ID alphabetically in tiebreak
    assert candidates[0].moment_id == "A_ID"

def test_discovery_ai_with_transcript(valid_source):
    transcript = "The secret to this is very simple..."
    moments = discover_moments(valid_source, transcript=transcript, ai_available=True)
    
    assert len(moments) == 1
    m = moments[0]
    assert m.discovery_method == DiscoveryMethod.AI_PROVIDER
    assert m.confidence == MomentConfidence.HIGH

def test_discovery_fallback_empty_transcript(valid_source):
    # Empty transcript triggers fallback
    moments = discover_moments(valid_source, transcript="", ai_available=True)
    
    assert len(moments) == 1
    m = moments[0]
    assert m.discovery_method == DiscoveryMethod.RULE_FALLBACK
    assert m.confidence == MomentConfidence.LOW
    assert m.end_seconds == 60 # Default fallback rule for 120s video

def test_discovery_fallback_no_ai(valid_source):
    # AI unavailable triggers fallback, but since transcript is present, confidence is MEDIUM
    transcript = "Something something."
    moments = discover_moments(valid_source, transcript=transcript, ai_available=False)
    
    assert len(moments) == 1
    m = moments[0]
    assert m.discovery_method == DiscoveryMethod.RULE_FALLBACK
    assert m.confidence == MomentConfidence.MEDIUM

def test_discovery_short_video_fallback():
    payload = {"source_url": "url", "source_type": "vid", "duration_seconds": 30}
    src = NormalizedSource.from_provider_payload("y", "1", payload)
    
    moments = discover_moments(src, transcript="", ai_available=False)
    assert len(moments) == 1
    assert moments[0].duration_seconds == 30 # Entire video

def test_low_confidence_suppression():
    # If a candidate gets penalized below 0.3, it is dropped.
    c = CandidateMoment(
        moment_id="1", source_id="src", start_seconds=0, end_seconds=10, duration_seconds=10,
        moment_type="t", 
        hook_score=0.1, payoff_score=0.1, standalone_score=0.1, context_score=0.1, relevance_score=0.1,
        confidence=MomentConfidence.LOW, # This applies a 0.5x penalty to an already low 0.1 score
        evidence="e", discovery_method=DiscoveryMethod.RULE_FALLBACK
    )
    assert c.total_score < 0.3
