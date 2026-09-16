from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

EvidenceLevel = Literal[
    "hypothesis",
    "single_signal",
    "repeated_signal",
    "explicit_request",
    "observed_purchase",
    "repeat_purchase",
]

OpportunityState = Literal[
    "discovered",
    "validated",
    "rejected",
    "ready_to_build",
    "building",
    "ready_to_launch",
    "launched",
    "scaling",
    "killed",
]

ActionType = Literal[
    "collect_signal",
    "validate_demand",
    "research_buyer",
    "research_distributor",
    "draft_offer",
    "repair_offer",
    "complete_proof",
    "complete_creative",
    "build_product",
    "qa_product",
    "launch_experiment",
    "follow_up_sales",
    "optimize_offer",
    "scale_winner",
    "kill_opportunity",
]

EVIDENCE_WEIGHT: dict[EvidenceLevel, float] = {
    "hypothesis": 0.10,
    "single_signal": 0.25,
    "repeated_signal": 0.45,
    "explicit_request": 0.65,
    "observed_purchase": 0.85,
    "repeat_purchase": 1.00,
}


@dataclass(slots=True)
class DemandSignal:
    signal_id: str
    source: str
    problem: str
    evidence_level: EvidenceLevel
    buyer_segment: str = "unknown"
    distributor_hint: str | None = None
    recency_days: int = 0
    engagement: float = 0.0
    purchase_intent: float = 0.0
    evidence: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def evidence_weight(self) -> float:
        return EVIDENCE_WEIGHT[self.evidence_level]


@dataclass(slots=True)
class OfferCandidate:
    offer_id: str
    problem: str
    promise: str
    format: str
    price: float
    gross_margin: float
    production_cost: float
    acquisition_cost: float = 0.0
    repeat_potential: float = 0.0
    expansion_potential: float = 0.0
    distributor_fit: float = 0.0
    distribution_probability: float = 0.0
    evidence_quality: float = 0.0


@dataclass(slots=True)
class Opportunity:
    opportunity_id: str
    problem: str
    buyer_segment: str
    distributor_type: str
    state: OpportunityState = "discovered"
    demand_strength: float = 0.0
    pain_intensity: float = 0.0
    buyer_intent: float = 0.0
    audience_access: float = 0.0
    distribution_probability: float = 0.0
    price_potential: float = 0.0
    gross_margin: float = 0.0
    repeat_potential: float = 0.0
    expansion_potential: float = 0.0
    evidence_quality: float = 0.0
    production_cost: float = 0.0
    acquisition_cost: float = 0.0
    risk: float = 0.0
    expected_value: float = 0.0
    confidence: float = 0.0
    evidence_ids: list[str] = field(default_factory=list)
    offer_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def score(self) -> float:
        numerator = (
            self.demand_strength
            * self.pain_intensity
            * self.buyer_intent
            * max(self.audience_access, 0.05)
            * max(self.distribution_probability, 0.05)
            * max(self.price_potential, 0.05)
            * max(self.gross_margin, 0.05)
            * max(self.repeat_potential, 0.05)
            * max(self.expansion_potential, 0.05)
            * max(self.evidence_quality, 0.05)
        )
        denominator = max(self.production_cost + self.acquisition_cost + self.risk, 0.05)
        self.expected_value = numerator / denominator
        self.confidence = min(
            1.0,
            0.5 * self.evidence_quality + 0.25 * self.distribution_probability + 0.25 * self.buyer_intent,
        )
        return self.expected_value * self.confidence

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class ConvictionAssessment:
    relevance: float = 0.0
    outcome_clarity: float = 0.0
    proof: float = 0.0
    risk_reduction: float = 0.0
    purchase_friction: float = 0.0
    creative_readiness: float = 0.0
    personalization: float = 0.0
    trust: float = 0.0
    usage_readiness: float = 0.0
    claim_integrity: float = 0.0

    def scores(self) -> dict[str, float]:
        return asdict(self)


@dataclass(slots=True)
class ConvictionGateResult:
    status: Literal["blocked", "repair", "ready"]
    score: float
    passed_gates: list[str] = field(default_factory=list)
    failed_gates: list[str] = field(default_factory=list)
    next_action: str = "validate_demand"
    reasons: list[str] = field(default_factory=list)


@dataclass(slots=True)
class Decision:
    decision_id: str
    opportunity_id: str
    action: ActionType
    rationale: dict[str, Any]
    expected_value: float
    confidence: float
    validation_plan: list[str] = field(default_factory=list)
    kill_conditions: list[str] = field(default_factory=list)
    owner: str = "system"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
