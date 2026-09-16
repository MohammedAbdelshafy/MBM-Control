from __future__ import annotations
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

PainFamily = Literal[
    "operational_friction",
    "revenue_leak",
    "market_access",
    "knowledge_retrieval",
    "workflow_coordination"
]

MaturityState = Literal[
    "candidate",
    "validated",
    "winner",
    "rejected"
]

@dataclass(slots=True)
class Event:
    event_id: str
    event_type: str
    timestamp: str
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass(slots=True)
class PainCandidate:
    candidate_id: str
    pain_family: PainFamily
    description: str
    target_market: str
    discovered_at: str
    independence_key: str
    events: list[Event] = field(default_factory=list)
    state: MaturityState = "candidate"
    score: float = 0.0

    def append_event(self, event: Event) -> None:
        self.events.append(event)
        self._derive_maturity()

    def _derive_maturity(self) -> None:
        """Derive maturity state from append-only outcome events."""
        # Simple derivation logic: 
        # Refund/Churn -> rejected
        # Payment/Closed_Won -> winner (if multiple) or validated
        
        has_payment = False
        has_refund = False
        
        for e in self.events:
            if e.event_type in ("refund", "churn", "hard_rejection"):
                has_refund = True
            elif e.event_type in ("payment", "closed_won"):
                has_payment = True

        if has_refund:
            self.state = "rejected"
        elif has_payment:
            self.state = "winner"
        elif any(e.event_type == "demo_booked" for e in self.events):
            self.state = "validated"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
