"""Deterministic, explainable buyer matching. Demand is never inferred."""

from __future__ import annotations

from .materials import buyer_categories_for, normalize_material
from .models import BuyerMatch, BuyerProfile, FactoryWasteQuota


def _token_set(values: tuple[str, ...]) -> set[str]:
    return {" ".join(v.lower().split()) for v in values if v.strip()}


def match_buyer(quota: FactoryWasteQuota, buyer: BuyerProfile) -> BuyerMatch:
    errors = quota.validate()
    if errors:
        raise ValueError("; ".join(errors))

    material = normalize_material(quota.material)
    accepted = {normalize_material(x) for x in buyer.accepted_materials}
    reasons: list[str] = []
    missing: list[str] = []

    if material in accepted:
        score = 0.55
        reasons.append(f"material match: {material}")
    else:
        score = 0.0
        missing.append("verified acceptance of the exact material")

    categories = {c.lower() for c in buyer.buyer_categories}
    target_categories = {c.lower() for c in buyer_categories_for(material)}
    if categories & target_categories:
        score += 0.15
        reasons.append("buyer category aligns with material")

    quota_form = " ".join(quota.form.lower().split())
    forms = _token_set(buyer.accepted_forms)
    if quota_form and forms:
        if quota_form in forms:
            score += 0.15
            reasons.append("form is explicitly accepted")
        else:
            missing.append("confirmation that the buyer accepts the supplied form")
    elif quota_form:
        missing.append("buyer form acceptance")

    if buyer.geography and quota.geography:
        if buyer.geography.lower() in quota.geography.lower() or quota.geography.lower() in buyer.geography.lower():
            score += 0.05
            reasons.append("geography is compatible")
        else:
            missing.append("logistics/collection coverage")

    if buyer.evidence_urls:
        score += 0.10
        reasons.append("external evidence supplied")
    else:
        missing.append("public evidence URL")

    return BuyerMatch(
        quota=quota,
        buyer=buyer,
        score=round(min(score, 1.0), 3),
        reasons=tuple(reasons),
        missing_checks=tuple(dict.fromkeys(missing)),
    )


def rank_buyers(quota: FactoryWasteQuota, buyers: list[BuyerProfile]) -> list[BuyerMatch]:
    matches = [match_buyer(quota, buyer) for buyer in buyers]
    return sorted(matches, key=lambda item: (item.qualified, item.score), reverse=True)
