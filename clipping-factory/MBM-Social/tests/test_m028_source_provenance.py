import pytest
from mbm_social.models.source import NormalizedSource, ProvenanceConfidence

def test_source_valid_payload():
    payload = {
        "source_url": "https://youtube.com/watch?v=123",
        "source_type": "video",
        "title": "Test Video",
        "creator": "Test Creator",
        "duration_seconds": 120,
        "language": "en",
        "provenance_confidence": "HIGH"
    }
    
    source = NormalizedSource.from_provider_payload("youtube", "123", payload)
    
    assert source.source_id == "youtube_123"
    assert source.provider == "youtube"
    assert source.provider_object_id == "123"
    assert source.source_url == "https://youtube.com/watch?v=123"
    assert source.title == "Test Video"
    assert source.duration_seconds == 120
    assert source.provenance_confidence == ProvenanceConfidence.HIGH
    assert source.raw_metadata_hash is not None
    assert source.content_hash is not None

def test_source_missing_metadata():
    payload = {} # Completely empty
    source = NormalizedSource.from_provider_payload("podcast_api", "abc", payload)
    
    assert source.source_id == "podcast_api_abc"
    assert source.title is None
    assert source.source_url is None
    assert source.creator is None
    assert source.duration_seconds is None
    assert source.provenance_confidence == ProvenanceConfidence.UNKNOWN

def test_source_duplicate_deterministic_hash():
    payload = {"title": "Same Title"}
    
    source1 = NormalizedSource.from_provider_payload("provider", "id1", payload)
    source2 = NormalizedSource.from_provider_payload("provider", "id1", payload)
    
    assert source1.source_id == source2.source_id
    assert source1.raw_metadata_hash == source2.raw_metadata_hash
    assert source1.content_hash == source2.content_hash

def test_source_changed_metadata_hash():
    payload1 = {"title": "Title A"}
    payload2 = {"title": "Title B"}
    
    source1 = NormalizedSource.from_provider_payload("provider", "id1", payload1)
    source2 = NormalizedSource.from_provider_payload("provider", "id1", payload2)
    
    assert source1.source_id == source2.source_id
    # Metadata hashes should differ because the payload changed
    assert source1.raw_metadata_hash != source2.raw_metadata_hash
    # Content hash (fallback) relies on source_id, so it remains the same
    assert source1.content_hash == source2.content_hash

def test_source_content_bytes_hash():
    payload = {"title": "Title"}
    content1 = b"video_data_1"
    content2 = b"video_data_2"
    
    source1 = NormalizedSource.from_provider_payload("provider", "id1", payload, content_bytes=content1)
    source2 = NormalizedSource.from_provider_payload("provider", "id1", payload, content_bytes=content2)
    
    # Metadata is identical
    assert source1.raw_metadata_hash == source2.raw_metadata_hash
    # Content bytes differ
    assert source1.content_hash != source2.content_hash

def test_source_malformed_payload():
    class Unserializable:
        pass
        
    payload = {"title": Unserializable()}
    
    with pytest.raises(ValueError, match="Malformed provider payload: contains non-serializable objects"):
        NormalizedSource.from_provider_payload("provider", "id1", payload)

def test_source_missing_provider():
    with pytest.raises(ValueError, match="Provider and provider_object_id are required"):
        NormalizedSource.from_provider_payload("", "id1", {})
