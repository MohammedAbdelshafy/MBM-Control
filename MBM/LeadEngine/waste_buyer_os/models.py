"""Domain models for the factory-waste buyer pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class FactoryWasteQuota:
    """A monthly factory waste stream.

    Values are descriptive. No buyer or price is inferred when the factory
    has not supplied it.
    """

    material: str
    kg_per_month: float
    form: str = ""
    grade: str = ""
    contamination: str = ""
    geography: str = "Egypt"
    current_disposition: str = ""
    asking_price_egp_per_kg: float | None = None
    available_from: str | None = None
    evidence: tuple[str, ...] = field(default_factory=tuple)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if not self.material.strip():
            errors.append("material is required")
        if self.kg_per_month <= 0:
            errors.append("kg_per_month must be greater than zero")
        if self.asking_price_egp_per_kg is not None and self.asking_price_egp_per_kg < 0:
            errors.append("asking_price_egp_per_kg cannot be negative")
        return errors


@dataclass(frozen=True)
class BuyerProfile:
    """A buyer/recycler discovered from an external source.

    evidence_urls should contain URLs proving the company handles the
    relevant material. A company name alone is not proof.
    """

    company_name: str
    website: str = ""
    geography: str = "Egypt"
    buyer_categories: tuple[str, ...] = field(default_factory=tuple)
    accepted_materials: tuple[str, ...] = field(default_factory=tuple)
    accepted_forms: tuple[str, ...] = field(default_factory=tuple)
    evidence_urls: tuple[str, ...] = field(default_factory=tuple)
    notes: str = ""
    decision_maker_role: str = ""

    @property
    def verified(self) -> bool:
        return bool(self.company_name.strip() and self.evidence_urls)


@dataclass(frozen=True)
class BuyerMatch:
    quota: FactoryWasteQuota
    buyer: BuyerProfile
    score: float
    reasons: tuple[str, ...]
    missing_checks: tuple[str, ...] = field(default_factory=tuple)

    @property
    def qualified(self) -> bool:
        return self.buyer.verified and self.score >= 0.70 and not self.missing_checks


def to_dict(obj: Any) -> dict[str, Any]:
    if hasattr(obj, "__dataclass_fields__"):
        from dataclasses import asdict
        return asdict(obj)
    raise TypeError(f"Unsupported object: {type(obj)!r}")
