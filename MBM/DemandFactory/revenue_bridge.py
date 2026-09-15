from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class RevenueEvent:
    """Canonical proposal/record shape for a real commercial event.

    No revenue is inferred.  A RevenueEvent is valid only when the source
    system supplies a transaction reference and monetary amount.
    """

    transaction_id: str
    opportunity_id: str
    offer_id: str
    product_id: str
    distributor_id: str = ""
    channel: str = ""
    campaign: str = ""
    checkout_reference: str = ""
    gross_revenue: float = 0.0
    net_revenue: float | None = None
    currency: str = "USD"
    occurred_at: str = ""
    source: str = ""
    evidence_level: str = "observed_purchase"

    def validate(self) -> None:
        required = {
            "transaction_id": self.transaction_id,
            "opportunity_id": self.opportunity_id,
            "offer_id": self.offer_id,
            "product_id": self.product_id,
            "checkout_reference": self.checkout_reference,
            "source": self.source,
        }
        missing = [name for name, value in required.items() if not str(value).strip()]
        if missing:
            raise ValueError(f"revenue event missing required fields: {', '.join(missing)}")
        if self.gross_revenue <= 0:
            raise ValueError("gross_revenue must be greater than zero for an observed purchase")
        if not self.currency.strip():
            raise ValueError("currency is required")
        if self.evidence_level not in {"observed_purchase", "repeat_purchase"}:
            raise ValueError("a recorded transaction requires purchase-level evidence")

    def to_dict(self) -> dict[str, Any]:
        self.validate()
        return asdict(self)


def build_revenue_event(**kwargs: Any) -> RevenueEvent:
    """Normalize a provider transaction into the canonical revenue contract."""
    event = RevenueEvent(
        occurred_at=kwargs.pop("occurred_at", "") or datetime.now(timezone.utc).isoformat(),
        **kwargs,
    )
    event.validate()
    return event


def attribution_key(*, opportunity_id: str, offer_id: str, product_id: str, distributor_id: str = "", channel: str = "") -> str:
    parts = [opportunity_id, offer_id, product_id, distributor_id, channel]
    return "revenue:" + ":".join(part.replace(":", "_") for part in parts if part)
