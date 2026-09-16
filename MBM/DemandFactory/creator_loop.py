from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal

CreatorStage = Literal[
    "discovered",
    "qualified",
    "invited",
    "sample_sent",
    "content_ready",
    "published",
    "converting",
    "retained",
    "declined",
]


@dataclass(slots=True)
class CreatorProfile:
    creator_id: str
    name: str
    audience_description: str
    audience_fit: float = 0.0
    trust_fit: float = 0.0
    commercial_fit: float = 0.0
    content_fit: float = 0.0
    reach: float = 0.0
    stage: CreatorStage = "discovered"
    preferred_channels: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def score(self) -> float:
        return (
            0.30 * self.audience_fit
            + 0.25 * self.trust_fit
            + 0.20 * self.commercial_fit
            + 0.15 * self.content_fit
            + 0.10 * self.reach
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(slots=True)
class CreatorOfferPack:
    opportunity_id: str
    product_id: str
    creator_id: str
    hook: str
    audience_problem: str
    demonstrated_outcome: str
    proof_assets: list[str] = field(default_factory=list)
    creative_assets: list[str] = field(default_factory=list)
    disclosure_required: bool = True
    compensation_model: str = "affiliate"
    commission_rate: float = 0.20
    tracking_key: str = ""
    creator_feedback_questions: list[str] = field(default_factory=lambda: [
        "What part of this offer feels most useful to your audience?",
        "What objection would your audience raise before buying?",
        "What would make the demonstration more credible?",
    ])

    def to_dict(self) -> dict:
        return asdict(self)


def qualify_creator(creator: CreatorProfile, *, minimum_score: float = 0.62) -> bool:
    return creator.score() >= minimum_score


def qualify_creator_with_evidence_gate(
    creator: CreatorProfile,
    evidence: dict | object,
    *,
    minimum_score: float = 0.62,
    now=None,
):
    """Evidence-first acquisition integration (#65).

    Runs the deterministic 20,000-evidenced-audience gate FIRST
    (fail-closed), then the fit-score threshold. Audience size is never
    mapped to buyer intent, conversion, revenue, or PMF.
    """
    from .creator_gate import qualify_creator_with_evidence as _gate

    return _gate(creator.score(), evidence, minimum_score=minimum_score, now=now)


def build_creator_pack(
    creator: CreatorProfile,
    *,
    opportunity_id: str,
    product_id: str,
    hook: str,
    audience_problem: str,
    demonstrated_outcome: str,
    proof_assets: list[str],
    creative_assets: list[str],
    commission_rate: float = 0.20,
) -> CreatorOfferPack:
    return CreatorOfferPack(
        opportunity_id=opportunity_id,
        product_id=product_id,
        creator_id=creator.creator_id,
        hook=hook,
        audience_problem=audience_problem,
        demonstrated_outcome=demonstrated_outcome,
        proof_assets=proof_assets,
        creative_assets=creative_assets,
        commission_rate=commission_rate,
        tracking_key=f"creator:{creator.creator_id}:product:{product_id}",
    )
