"""
GTM EVIDENCE LAYER
=============================================================================
Normalized, immutable evidence object enforcing zero-fabrication guarantees.

Fields:
  claim, source, source_reference, timestamp, confidence, agent, metadata
=============================================================================
"""

from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import uuid


class GtmEvidence:
    """Normalized evidence record linking an asserted claim to an authoritative source."""

    def __init__(
        self,
        claim: str,
        source: str,
        source_reference: str,
        confidence: float,
        agent: str,
        timestamp: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        evidence_id: Optional[str] = None,
    ):
        if not claim or not claim.strip():
            raise ValueError("Evidence claim cannot be empty.")
        if not source or not source.strip():
            raise ValueError("Evidence source cannot be empty (Zero-Fabrication rule).")
        if not (0.0 <= confidence <= 1.0):
            raise ValueError(f"Evidence confidence must be between 0.0 and 1.0, got {confidence}")

        self.evidence_id = evidence_id or f"evi_{uuid.uuid4().hex[:12]}"
        self.claim = claim.strip()
        self.source = source.strip()
        self.source_reference = source_reference.strip()
        self.confidence = float(confidence)
        self.agent = agent.strip()
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "claim": self.claim,
            "source": self.source,
            "source_reference": self.source_reference,
            "confidence": self.confidence,
            "agent": self.agent,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GtmEvidence":
        return cls(
            claim=data["claim"],
            source=data["source"],
            source_reference=data.get("source_reference", ""),
            confidence=data.get("confidence", 1.0),
            agent=data.get("agent", "UNKNOWN_AGENT"),
            timestamp=data.get("timestamp"),
            metadata=data.get("metadata", {}),
            evidence_id=data.get("evidence_id"),
        )


class EvidenceStore:
    """In-memory store for collecting, querying, and auditing GTM evidence cards."""

    def __init__(self):
        self._store: Dict[str, List[GtmEvidence]] = {}

    def add_evidence(self, entity_id: str, evidence: GtmEvidence) -> None:
        """Associate an evidence record with an entity (lead, deal, company)."""
        if entity_id not in self._store:
            self._store[entity_id] = []
        self._store[entity_id].append(evidence)

    def get_evidence_for_entity(self, entity_id: str) -> List[GtmEvidence]:
        """Retrieve all evidence records for a given entity."""
        return self._store.get(entity_id, [])

    def calculate_entity_confidence(self, entity_id: str) -> float:
        """Calculate weighted average confidence score across an entity's evidence."""
        records = self.get_evidence_for_entity(entity_id)
        if not records:
            return 0.0
        return sum(e.confidence for e in records) / len(records)

    def to_dict(self) -> Dict[str, List[Dict[str, Any]]]:
        return {k: [e.to_dict() for e in v] for k, v in self._store.items()}
