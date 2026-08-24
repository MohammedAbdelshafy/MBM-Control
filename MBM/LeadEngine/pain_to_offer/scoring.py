"""scoring -- deterministic pain scoring.

Pure function of the pack's pain evidence statuses. Targeting facts
(locations, size, phone) contribute NOTHING to the score: PRIORITY != PROOF.
Same input always yields the same output and the same ranking order.
"""
from __future__ import annotations

from collections.abc import Iterable

from pain_to_offer.schema import CompanyEvidencePack, EvidenceStatus

WEIGHTS = {
    EvidenceStatus.PROVEN: 40,
    EvidenceStatus.LEADING_HYPOTHESIS: 15,
    EvidenceStatus.UNVERIFIED: 0,
    EvidenceStatus.REJECTED: 0,
}

MAX_SCORE = 100


def pain_score(pack: CompanyEvidencePack) -> int:
    if not pack.has_supported_pain():
        return 0
    if pack.pain_hypothesis not in (EvidenceStatus.PROVEN, EvidenceStatus.LEADING_HYPOTHESIS):
        return 0
    raw = sum(WEIGHTS[c.status] for c in pack.pain_evidence)
    return min(MAX_SCORE, raw)


STATUS_FACTOR = {
    EvidenceStatus.PROVEN: 1.0,
    EvidenceStatus.LEADING_HYPOTHESIS: 0.75,
    EvidenceStatus.UNVERIFIED: 0.0,
    EvidenceStatus.REJECTED: 0.0,
}


def weighted_pain_score(pack: CompanyEvidencePack) -> int:
    """Deterministic commercial score from RECORDED data only.

    score = 100 * recorded pain_confidence * status_factor.
    No external inputs; same pack always yields the same integer.
    """
    factor = STATUS_FACTOR[pack.pain_hypothesis]
    if factor == 0.0:
        return 0
    confidence = min(max(pack.pain_confidence, 0.0), 1.0)
    return round(MAX_SCORE * confidence * factor)


def rank_packs(packs: Iterable[CompanyEvidencePack]) -> list[tuple[CompanyEvidencePack, int]]:
    """Deterministic ordering: score desc, then company_id asc."""
    scored = [(p, pain_score(p)) for p in packs]
    scored.sort(key=lambda pair: (-pair[1], pair[0].company_id))
    return scored
