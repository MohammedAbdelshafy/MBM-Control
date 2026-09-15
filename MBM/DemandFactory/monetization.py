from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class MonetizationPlan:
    opportunity_id: str
    product_name: str
    mechanism: str
    buyer_outcome: str
    proof_assets: list[str] = field(default_factory=list)
    risk_reducers: list[str] = field(default_factory=list)
    delivery_assets: list[str] = field(default_factory=list)
    checkout_rails: list[str] = field(default_factory=list)
    acquisition_channels: list[str] = field(default_factory=list)
    price: float = 0.0
    recurring: bool = False
    launch_ready: bool = False
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_monetization_plan(opportunity: Any, *, product_name: str | None = None) -> MonetizationPlan:
    """Translate a scored opportunity into a transaction-oriented launch plan.

    This function remains provider-neutral and proposal-only. It selects existing
    MBM money rails rather than pretending a new checkout system is required.
    """
    name = product_name or f"{opportunity.problem.title()} System"
    metadata = getattr(opportunity, "metadata", {}) or {}
    price = float(metadata.get("launch_price", opportunity.price_potential or 0.0))
    plan = MonetizationPlan(
        opportunity_id=opportunity.opportunity_id,
        product_name=name,
        mechanism=metadata.get("mechanism", "workflow + assets + implementation guidance"),
        buyer_outcome=metadata.get("buyer_outcome", opportunity.problem),
        price=price,
        recurring=bool(metadata.get("recurring", False)),
        proof_assets=list(metadata.get("proof_assets", [])),
        risk_reducers=list(metadata.get("risk_reducers", [])),
        delivery_assets=list(metadata.get("delivery_assets", [])),
        checkout_rails=list(metadata.get("checkout_rails", ["whop"])),
        acquisition_channels=list(metadata.get("acquisition_channels", ["direct", "affiliate", "creator"])),
    )

    if not plan.buyer_outcome.strip():
        plan.blockers.append("buyer_outcome_missing")
    if not plan.proof_assets:
        plan.blockers.append("proof_missing")
    if not plan.delivery_assets:
        plan.blockers.append("delivery_assets_missing")
    if plan.price <= 0:
        plan.blockers.append("price_missing")
    if not plan.checkout_rails:
        plan.blockers.append("checkout_rail_missing")
    plan.launch_ready = not plan.blockers
    return plan
