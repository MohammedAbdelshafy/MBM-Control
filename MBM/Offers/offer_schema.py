"""Revenue/Productized Offers evidence-first schema (#64).

Preserves evidence-first offer schemas. Provides the minimum end-to-end
offer validation path without fabricating market data.

Rules (deterministic, fail-closed):
- Required: offer_id, problem, buyer_segment, promise, format, price,
  proof_assets, evidence_ids, evidence_level, limitations,
  checkout_rail, delivery_assets.
- Forbidden fabricated claims without evidence:
  market size, ROI, savings, traction, testimonials, revenue,
  customer counts, guarantees.
- Consequential commercial actions (publish, charge, send, deploy)
  are proposal-only and require human approval. This module never
  executes them.

Legacy MBM/Offers/*.md files are NOT auto-validated; they must pass
this schema before any commercial use. Known: current legacy markdown
offers contain unsupported market/ROI claims and FAIL validation
(documented, not silently approved).
"""

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

EVIDENCE_RANK: dict[str, int] = {
    "hypothesis": 0,
    "single_signal": 1,
    "repeated_signal": 2,
    "explicit_request": 3,
    "observed_purchase": 4,
    "repeat_purchase": 5,
}

# Claim keywords that require evidence. Deterministic substring match.
FABRICATED_CLAIM_RULES: dict[str, list[str]] = {
    "FABRICATED_MARKET_DATA": ["$2.74b", "market size", "cagr", "% of marketing", "% of brands"],
    "FABRICATED_ROI": ["roi", "return on investment"],
    "FABRICATED_SAVINGS": ["savings", "save 94", "save 98", "% cheaper", "vs agency"],
    "FABRICATED_TRACTION": ["traction", "customers", "users", "mrr", "arr"],
    "FABRICATED_TESTIMONIAL": ["testimonial", "review:", "★★★★★", "5-star", "client said"],
    "FABRICATED_REVENUE": ["revenue", "$497/mo", "$997", "$1,997", "pricing plan"],
    "FABRICATED_GUARANTEE": ["guarantee", "money-back", "cancel anytime", "no risk"],
}


@dataclass(slots=True)
class ProductOffer:
    offer_id: str = ""
    problem: str = ""
    buyer_segment: str = ""
    promise: str = ""
    format: str = ""
    price: float = 0.0
    proof_assets: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    evidence_level: EvidenceLevel = "hypothesis"
    limitations: list[str] = field(default_factory=list)
    checkout_rail: str = ""
    delivery_assets: list[str] = field(default_factory=list)
    claims_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _contains_claim(text: str, keywords: list[str]) -> bool:
    lowered = (text or "").lower()
    return any(k in lowered for k in keywords)


def validate_offer(offer: ProductOffer | dict[str, Any]) -> list[str]:
    """Validate one offer. Empty = ready. Fail-closed."""
    if isinstance(offer, dict):
        offer = ProductOffer(
            offer_id=str(offer.get("offer_id", "")),
            problem=str(offer.get("problem", "")),
            buyer_segment=str(offer.get("buyer_segment", "")),
            promise=str(offer.get("promise", "")),
            format=str(offer.get("format", "")),
            price=float(offer.get("price", 0.0) or 0.0),
            proof_assets=list(offer.get("proof_assets", []) or []),
            evidence_ids=list(offer.get("evidence_ids", []) or []),
            evidence_level=offer.get("evidence_level", "hypothesis"),
            limitations=list(offer.get("limitations", []) or []),
            checkout_rail=str(offer.get("checkout_rail", "")),
            delivery_assets=list(offer.get("delivery_assets", []) or []),
            claims_text=str(offer.get("claims_text", "")),
        )
    failures: list[str] = []
    if not offer.offer_id.strip():
        failures.append("offer_missing_id")
    if not offer.problem.strip():
        failures.append("offer_missing_problem")
    if not offer.buyer_segment.strip():
        failures.append("offer_missing_buyer_segment")
    if not offer.promise.strip():
        failures.append("offer_missing_promise")
    if not offer.format.strip():
        failures.append("offer_missing_format")
    if offer.price <= 0:
        failures.append("offer_missing_price")
    if not offer.proof_assets:
        failures.append("offer_missing_proof")
    if not offer.evidence_ids:
        failures.append("offer_missing_evidence")
    if offer.evidence_level not in EVIDENCE_RANK:
        failures.append("offer_unknown_evidence_level")
    if not offer.limitations:
        failures.append("offer_missing_limitations")
    if not offer.checkout_rail.strip():
        failures.append("offer_missing_checkout_rail")
    if not offer.delivery_assets:
        failures.append("offer_missing_delivery")

    # Fabricated-claim gate: claims_text + promise inspected.
    searchable = f"{offer.claims_text} {offer.promise}"
    has_evidence = bool(offer.evidence_ids) and EVIDENCE_RANK.get(offer.evidence_level, 0) >= EVIDENCE_RANK["explicit_request"]
    # Proof assets alone do not substantiate market/ROI/revenue claims;
    # require explicit_request+ evidence. If below threshold, any such
    # claim is fabricated.
    if not has_evidence:
        for code, keywords in FABRICATED_CLAIM_RULES.items():
            if _contains_claim(searchable, keywords):
                failures.append(code)
    else:
        # Even with evidence, revenue/guarantee claims need purchase-level proof.
        purchase_level = EVIDENCE_RANK.get(offer.evidence_level, 0) >= EVIDENCE_RANK["observed_purchase"]
        if not purchase_level:
            for code in ("FABRICATED_REVENUE", "FABRICATED_GUARANTEE", "FABRICATED_TESTIMONIAL"):
                if _contains_claim(searchable, FABRICATED_CLAIM_RULES[code]):
                    failures.append(code)
    return sorted(set(failures))


def offer_readiness(offer: ProductOffer | dict[str, Any]) -> dict[str, Any]:
    failures = validate_offer(offer)
    return {"ready": not failures, "failures": failures}


def validate_offer_end_to_end(
    offer: ProductOffer | dict[str, Any],
    *,
    conviction_status: str = "ready",
    qa_failures: list[str] | None = None,
) -> dict[str, Any]:
    """Minimum end-to-end offer validation path.

    offer -> conviction -> QA -> release-manifest shape.
    Returns proposal-only readiness; never executes publish/charge/send.
    Consequential actions remain human-controlled (approval required
    downstream in lifecycle.can_publish).
    """
    from MBM.DemandFactory.lifecycle import run_qa

    if isinstance(offer, dict):
        offer_obj = ProductOffer(
            offer_id=str(offer.get("offer_id", "")),
            problem=str(offer.get("problem", "")),
            buyer_segment=str(offer.get("buyer_segment", "")),
            promise=str(offer.get("promise", "")),
            format=str(offer.get("format", "")),
            price=float(offer.get("price", 0.0) or 0.0),
            proof_assets=list(offer.get("proof_assets", []) or []),
            evidence_ids=list(offer.get("evidence_ids", []) or []),
            evidence_level=offer.get("evidence_level", "hypothesis"),
            limitations=list(offer.get("limitations", []) or []),
            checkout_rail=str(offer.get("checkout_rail", "")),
            delivery_assets=list(offer.get("delivery_assets", []) or []),
            claims_text=str(offer.get("claims_text", "")),
        )
    else:
        offer_obj = offer
    offer_failures = validate_offer(offer_obj)
    qa = run_qa(
        quality_failures=list(qa_failures or []),
        conviction_status=conviction_status,
        evidence_ids=list(offer_obj.evidence_ids),
        evidence_quality=0.8 if offer_obj.evidence_ids else 0.0,
        commercial_score=1.0 if offer_obj.price > 0 else 0.0,
        confidence=0.8 if offer_obj.evidence_ids else 0.0,
    )
    ready = not offer_failures and qa.passed
    return {
        "offer_id": offer_obj.offer_id,
        "offer_failures": offer_failures,
        "qa_passed": qa.passed,
        "qa_failures": qa.failures,
        "ready": ready,
        "execution": "proposal_only_human_approval_required",
    }
