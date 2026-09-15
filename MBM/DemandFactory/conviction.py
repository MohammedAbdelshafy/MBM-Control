from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ConvictionResult:
    score: float
    blockers: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    next_actions: list[str] = field(default_factory=list)

    @property
    def launch_ready(self) -> bool:
        return self.score >= 0.78 and not self.blockers

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": round(self.score, 4),
            "launch_ready": self.launch_ready,
            "blockers": self.blockers,
            "strengths": self.strengths,
            "next_actions": self.next_actions,
        }


REQUIRED = {
    "relevance": 0.15,
    "outcome_clarity": 0.15,
    "proof": 0.15,
    "risk_reduction": 0.10,
    "purchase_friction": 0.10,
    "creative_readiness": 0.10,
    "personalization": 0.10,
    "trust": 0.10,
    "usage_readiness": 0.05,
}


def evaluate_conviction(metadata: dict[str, Any] | None = None) -> ConvictionResult:
    """Score legitimate purchase confidence from explicit product evidence.

    Values are expected to be normalized 0..1. Missing critical evidence becomes
    a blocker instead of being silently treated as a passing score.
    """
    data = metadata or {}
    strengths: list[str] = []
    blockers: list[str] = []
    next_actions: list[str] = []

    total = 0.0
    for key, weight in REQUIRED.items():
        raw = data.get(key)
        try:
            value = max(0.0, min(1.0, float(raw))) if raw is not None else 0.0
        except (TypeError, ValueError):
            value = 0.0
        total += value * weight
        if value >= 0.8:
            strengths.append(key)
        if value < 0.6:
            blockers.append(f"{key}_weak")
            next_actions.append(_repair_action(key))

    # Truthfulness is a hard gate, not a weighted preference.
    claims_verified = bool(data.get("claims_verified", False))
    proof_provenance = bool(data.get("proof_provenance", False))
    if not claims_verified:
        blockers.append("claims_not_verified")
        next_actions.append("verify_claims")
    if not proof_provenance:
        blockers.append("proof_provenance_missing")
        next_actions.append("attach_proof_provenance")

    # A checkout path and fulfillment path must be real before launch.
    if not data.get("checkout_rails"):
        blockers.append("checkout_rail_missing")
        next_actions.append("configure_checkout")
    if not data.get("delivery_assets"):
        blockers.append("delivery_assets_missing")
        next_actions.append("complete_delivery")

    return ConvictionResult(
        score=min(1.0, total),
        blockers=list(dict.fromkeys(blockers)),
        strengths=list(dict.fromkeys(strengths)),
        next_actions=list(dict.fromkeys(next_actions)),
    )


def _repair_action(key: str) -> str:
    mapping = {
        "relevance": "tighten_buyer_fit",
        "outcome_clarity": "clarify_buyer_outcome",
        "proof": "complete_proof",
        "risk_reduction": "add_risk_reduction",
        "purchase_friction": "remove_purchase_friction",
        "creative_readiness": "produce_core_creative",
        "personalization": "add_segment_personalization",
        "trust": "strengthen_trust_signals",
        "usage_readiness": "improve_onboarding",
    }
    return mapping.get(key, f"repair_{key}")
