import hashlib
import json
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from enum import Enum
from datetime import datetime, timezone

class ProvenanceConfidence(Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    UNKNOWN = "UNKNOWN"

@dataclass
class NormalizedSource:
    """
    Canonical provenance layer for reward-clipping inputs.
    """
    source_id: str  # Deterministic ID combining provider and object ID
    provider: str
    provider_object_id: str
    
    source_url: Optional[str]
    source_type: str  # e.g., "video", "podcast", "article"
    title: Optional[str]
    creator: Optional[str]
    
    captured_at: str  # ISO timestamp
    published_at: Optional[str]  # ISO timestamp
    
    duration_seconds: Optional[int]
    language: Optional[str]
    
    raw_metadata_hash: str
    content_hash: str
    
    provenance_confidence: ProvenanceConfidence
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_provider_payload(
        cls, 
        provider: str, 
        provider_object_id: str, 
        payload: Dict[str, Any],
        content_bytes: Optional[bytes] = None
    ) -> "NormalizedSource":
        """
        Creates a deterministic NormalizedSource from a provider payload.
        """
        if not provider or not provider_object_id:
            raise ValueError("Provider and provider_object_id are required for provenance")
            
        source_id = f"{provider}_{provider_object_id}"
        
        # Deterministic hashing of raw metadata
        # We sort keys to ensure identical payloads produce identical hashes
        try:
            payload_json = json.dumps(payload, sort_keys=True)
            raw_hash = hashlib.sha256(payload_json.encode('utf-8')).hexdigest()
        except TypeError:
            raise ValueError("Malformed provider payload: contains non-serializable objects")
            
        # Deterministic content hashing
        # If content bytes are provided (e.g. downloaded video), hash them.
        # Otherwise, if we only have a URL, the content_hash acts as a placeholder
        # until the content is materialized.
        if content_bytes:
            content_hash = hashlib.sha256(content_bytes).hexdigest()
        else:
            # Fallback to hashing the unique provider object ID if content is not yet downloaded
            # This ensures identical sources still resolve to the same placeholder content identity.
            content_hash = hashlib.sha256(source_id.encode('utf-8')).hexdigest()
            
        confidence_str = payload.get("provenance_confidence", "UNKNOWN").upper()
        try:
            confidence = ProvenanceConfidence(confidence_str)
        except ValueError:
            confidence = ProvenanceConfidence.UNKNOWN
            
        # Ensure we don't silently fabricate missing values - explicit None
        return cls(
            source_id=source_id,
            provider=provider,
            provider_object_id=provider_object_id,
            source_url=payload.get("source_url") or None,
            source_type=payload.get("source_type", "unknown"),
            title=payload.get("title") or None,
            creator=payload.get("creator") or None,
            captured_at=datetime.now(timezone.utc).isoformat(timespec='seconds'),
            published_at=payload.get("published_at") or None,
            duration_seconds=int(payload["duration_seconds"]) if payload.get("duration_seconds") is not None else None,
            language=payload.get("language") or None,
            raw_metadata_hash=raw_hash,
            content_hash=content_hash,
            provenance_confidence=confidence,
            metadata=payload
        )
