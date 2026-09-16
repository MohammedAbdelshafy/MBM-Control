from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class RevenueRoute:
    rail: str
    reason: str
    required_assets: list[str] = field(default_factory=list)
    next_action: str = ""
    live_capability: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def choose_revenue_route(opportunity: Any, plan: Any) -> RevenueRoute:
    """Select the lowest-friction existing revenue rail from product shape.

    The router is proposal-only. It never creates a product, checkout, CRM deal,
    campaign, affiliate relationship, or message on its own.
    """
    metadata = getattr(opportunity, "metadata", {}) or {}
    channels = set(plan.checkout_rails or [])
    acquisition = set(plan.acquisition_channels or [])
    price = float(plan.price or 0)
    recurring = bool(plan.recurring)

    if "whop" in channels:
        if "affiliate" in acquisition or recurring:
            return RevenueRoute(
                rail="whop",
                reason="Existing Whop rail supports recurring plans, checkout, affiliate distribution, and revenue reporting.",
                required_assets=["product_listing", "pricing_plan", "checkout_configuration", "proof_assets", "delivery_assets"],
                next_action="configure_whop_offer",
                live_capability=True,
            )
        return RevenueRoute(
            rail="whop",
            reason="Whop provides an existing digital-product transaction path with low additional infrastructure cost.",
            required_assets=["product_listing", "pricing_plan", "checkout_configuration", "delivery_assets"],
            next_action="configure_whop_offer",
            live_capability=True,
        )

    if "shopify" in channels:
        return RevenueRoute(
            rail="shopify",
            reason="Physical or commerce-oriented product fits the existing Shopify catalog and fulfillment path.",
            required_assets=["product_listing", "price", "media", "fulfillment_policy"],
            next_action="configure_shopify_product",
            live_capability=True,
        )

    if price >= 1000 or metadata.get("service") or metadata.get("dfy"):
        return RevenueRoute(
            rail="high_ticket_dfy",
            reason="Higher-price or service-shaped offer is better validated through a direct sales / DFY motion before software scale.",
            required_assets=["offer_brief", "proof_assets", "sales_dossier", "delivery_scope"],
            next_action="prepare_dfy_sales_offer",
            live_capability=True,
        )

    if "affiliate" in acquisition:
        return RevenueRoute(
            rail="affiliate",
            reason="Partner distribution can validate demand without requiring a large owned audience.",
            required_assets=["partner_offer", "tracking", "proof_assets", "checkout_link"],
            next_action="prepare_affiliate_pack",
            live_capability=False,
        )

    return RevenueRoute(
        rail="direct_sales",
        reason="Use direct outreach or inbound sales as the lowest-dependency path when no specialized commerce rail is configured.",
        required_assets=["offer_brief", "proof_assets", "checkout_link_or_invoice", "follow_up_sequence"],
        next_action="prepare_direct_sales_pack",
        live_capability=True,
    )
