"""Won-deal fulfillment + behavior-triggered upsell rules."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def create_fulfillment_job(*, customer: Dict[str, Any], listing: Dict[str, Any],
                           package: Dict[str, Any],
                           branding: Optional[Dict[str, Any]] = None,
                           sla_days: int = 7) -> Dict[str, Any]:
    """Won -> Fulfillment job with all production requirements. No prices invented:
    price comes from the quoted package or stays None for CUSTOM_QUOTE."""
    now = datetime.now(timezone.utc)
    return {
        "doctype": "Fulfillment Job",
        "customer": customer.get("agent_name"),
        "agent_id": customer.get("agent_id") or customer.get("name"),
        "listing_id": listing.get("listing_id"),
        "listing_address": listing.get("address"),
        "package_code": package.get("code"),
        "quoted_price": package.get("price"),
        "required_assets": ["listing_photos_final", "brand_logo", "agent_headshot"],
        "branding": branding or {},
        "output_formats": ["9:16", "16:9", "1:1", "short_form_variants"],
        "assigned_workflow": "REAL_ESTATE_PROPERTY_VIDEO_FACTORY",
        "qa_status": "PENDING",
        "created_at": now.isoformat(),
        "due_at": (now + timedelta(days=sla_days)).isoformat(),
        "status": "QUEUED",
    }


def batch_jobs(customer: Dict[str, Any], listings: List[Dict[str, Any]],
               package: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [create_fulfillment_job(customer=customer, listing=l, package=package)
            for l in listings]


UPSELL_RULES = [
    {"trigger": "delivered_count>=1", "offer": "additional_property_videos",
     "why": "positive_delivery"},
    {"trigger": "delivered_count>=2", "offer": "short_form_social_clips",
     "why": "multi_listing_customer"},
    {"trigger": "deliveries_30d>=3", "offer": "monthly_content_subscription",
     "why": "sustained_volume"},
    {"trigger": "brokerage_package_customer", "offer": "listing_reels_bundle",
     "why": "brokerage_scale"},
    {"trigger": "delivered_count>=1", "offer": "agent_intro_video",
     "why": "personal_brand"},
]


def upsell_opportunities(delivery_history: Dict[str, Any]) -> List[Dict[str, str]]:
    """Behavior-derived only; empty history -> empty list.

    Trigger grammar: `key>=N` (numeric) or bare truthy key."""
    out: List[Dict[str, str]] = []

    def _matches(trigger: str) -> bool:
        if ">=" in trigger:
            key, _, floor = trigger.partition(">=")
            try:
                return int(delivery_history.get(key) or 0) >= int(floor)
            except ValueError:
                return False
        return bool(delivery_history.get(trigger))

    for rule in UPSELL_RULES:
        if _matches(rule["trigger"]):
            out.append({"offer": rule["offer"], "why": rule["why"]})
    return out
