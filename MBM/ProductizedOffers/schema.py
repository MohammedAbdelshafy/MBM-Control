from __future__ import annotations
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

OfferState = Literal[
    "draft",
    "validation_in_progress",
    "validated",
    "killed"
]

@dataclass(slots=True)
class ProductizedOffer:
    offer_id: str
    name: str
    target_market: str
    buyer_role: str
    customer_job: str
    problem_trigger: str
    promised_outcome: str
    scope: str
    deliverables: list[str]
    proof_asset: str
    entry_offer_price: float
    core_implementation_price: float
    qualification_criteria: list[str]
    rejection_criteria: list[str]
    approval_requirement: str
    payment_path: str
    success_metric: str
    retention_path: str
    acquisition_channels: list[str] = field(default_factory=list)
    state: OfferState = "draft"
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def validate_motion(self, demo_exists: bool, qualified_accounts: int, approved_assets: bool) -> bool:
        """Evaluates whether the offer has passed the validation motion."""
        if demo_exists and qualified_accounts >= 20 and approved_assets:
            self.state = "validated"
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
