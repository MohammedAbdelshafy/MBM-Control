from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class HubSpotCommercialAdapter:
    """Proposal-only HubSpot adapter. No API mutation occurs here."""

    source: str = "MBM.DemandFactory"

    def build_opportunity_payload(self, opportunity: dict[str, Any]) -> dict[str, Any]:
        return {"object_type": "DEAL", "source": self.source, "properties": self._commercial_properties(opportunity)}

    def build_deal_payload(self, opportunity: dict[str, Any], offer: dict[str, Any]) -> dict[str, Any]:
        properties = self._commercial_properties(opportunity)
        properties.update({
            "offer_id": str(offer.get("offer_id", "")),
            "product_format": str(offer.get("format", "")),
            "price": str(offer.get("price", "")),
            "distribution_probability": str(offer.get("distribution_probability", "")),
        })
        return {"object_type": "DEAL", "source": self.source, "properties": properties}

    def record_learning_event(self, *, opportunity_id: str, outcome: str, attribution: dict[str, str]) -> dict[str, Any]:
        return {
            "event_type": "factory_learning",
            "opportunity_id": opportunity_id,
            "outcome": outcome,
            "attribution": dict(attribution),
            "write_required": True,
        }

    @staticmethod
    def _commercial_properties(opportunity: dict[str, Any]) -> dict[str, str]:
        keys = (
            "opportunity_id",
            "problem",
            "buyer_segment",
            "distributor_type",
            "state",
            "expected_value",
            "confidence",
        )
        return {key: str(opportunity.get(key, "")) for key in keys}
