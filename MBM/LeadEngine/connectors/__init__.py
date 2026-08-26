"""Reusable connector contracts for MBM integrations.

These contracts are intentionally provider-neutral. Connectors enrich, execute,
or observe; they do not override canonical Dialer safety decisions.
"""

from .evidence import Evidence, EvidenceEnvelope, build_evidence
from .events import RevenueEvent, normalize_event

__all__ = [
    "Evidence",
    "EvidenceEnvelope",
    "RevenueEvent",
    "build_evidence",
    "normalize_event",
]
