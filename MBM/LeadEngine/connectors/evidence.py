"""Evidence envelopes shared by enrichment providers.

The envelope makes provenance explicit and prevents model/provider output from
being mistaken for verified contact truth.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping


@dataclass(frozen=True)
class Evidence:
    source: str
    observed_at: str
    field: str
    value: Any
    confidence: str = "UNKNOWN"
    reference: str | None = None

    def validate(self) -> None:
        if not self.source.strip():
            raise ValueError("evidence source is required")
        if not self.field.strip():
            raise ValueError("evidence field is required")
        datetime.fromisoformat(self.observed_at.replace("Z", "+00:00"))


@dataclass(frozen=True)
class EvidenceEnvelope:
    lead_id: str
    provider: str
    evidence: tuple[Evidence, ...] = field(default_factory=tuple)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def validate(self) -> None:
        if not self.lead_id.strip():
            raise ValueError("lead_id is required")
        if not self.provider.strip():
            raise ValueError("provider is required")
        datetime.fromisoformat(self.generated_at.replace("Z", "+00:00"))
        for item in self.evidence:
            item.validate()

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "lead_id": self.lead_id,
            "provider": self.provider,
            "generated_at": self.generated_at,
            "evidence": [
                {
                    "source": item.source,
                    "observed_at": item.observed_at,
                    "field": item.field,
                    "value": item.value,
                    "confidence": item.confidence,
                    "reference": item.reference,
                }
                for item in self.evidence
            ],
        }


def build_evidence(
    lead_id: str,
    provider: str,
    claims: Mapping[str, Any],
    *,
    source: str,
    confidence: str = "UNKNOWN",
    reference: str | None = None,
    observed_at: str | None = None,
) -> EvidenceEnvelope:
    """Build a validated, provenance-aware evidence envelope from provider claims."""
    stamp = observed_at or datetime.now(timezone.utc).isoformat()
    envelope = EvidenceEnvelope(
        lead_id=lead_id,
        provider=provider,
        evidence=tuple(
            Evidence(
                source=source,
                observed_at=stamp,
                field=str(key),
                value=value,
                confidence=confidence,
                reference=reference,
            )
            for key, value in claims.items()
        ),
        generated_at=stamp,
    )
    envelope.validate()
    return envelope
