"""Dialer script engine - configurable templates, dynamic tokens, objection
branches. NEVER fabricates: any missing dynamic token renders as an explicit
[NEEDS_REVIEW:<token>] marker instead of invented content (D-019).
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

PRIMARY_TEMPLATE = (
    "Hi {agent_name}, this is {operator} with Contec. "
    "I came across your listing at {listing_address}{brokerage_clause}. "
    "We produce short AI-powered property tour videos that make listings move faster. "
    "{sample_clause} "
    "Do you have two minutes to see what it could look like?"
)

OBJECTION_BRANCHES: Dict[str, str] = {
    "how_much": (
        "Packages are scoped per listing volume - single property, multi-property, "
        "or a monthly plan. I'll send exact numbers matched to your inventory; "
        "no pressure and no generic pricing."
    ),
    "have_videographer": (
        "Great - we complement, not replace. Agents use us for fast coverage on "
        "listings your videographer can't reach in time, or as A/B creative."
    ),
    "dont_need_video": (
        "Understood. Out of curiosity - when a listing sits, is it price or exposure? "
        "If exposure, one sample on your worst performer costs you nothing to look at."
    ),
    "send_it": (
        "Absolutely - what's the best email or mobile for the sample link? "
        "It's 30-45 seconds, watermark-free preview of {listing_address}."
    ),
    "how_it_works": (
        "You send the listing link (or we pull public photos), our pipeline builds "
        "the cinematic tour with your branding, you approve, then it's yours for "
        "portals and social. Turnaround is days, not weeks."
    ),
    "is_it_ai": (
        "Yes - AI assembles and animates from the real listing photos. Nothing about "
        "the property is invented; it's your actual asset presented cinematically."
    ),
    "multiple_listings": (
        "That's exactly where it gets cost-effective. Volume packages drop the "
        "per-listing price - if you have {active_listings} active now, I'll price that tier."
    ),
    "too_expensive": (
        "Fair. Let's start with one listing as a paid pilot so you can judge results "
        "before any commitment."
    ),
    "call_me_later": (
        "Of course - what date and time suit? I'll call then. ({callback_note})"
    ),
    "not_interested": (
        "No problem at all - thanks for your time. I'll leave the sample link anyway; "
        "if it's ever useful, it's yours."
    ),
}

_TOKEN_PATTERN = re.compile(r"\{([a-z_]+)\}")


def render_primary(agent: Dict[str, Any], listing: Dict[str, Any],
                   operator: str = "Contec") -> str:
    tokens = {
        "agent_name": agent.get("agent_name"),
        "brokerage_clause": f" over at {agent['brokerage']}" if agent.get("brokerage") else "",
        "listing_address": listing.get("address"),
        "sample_clause": (
            "I already had a sample cut for this exact property. "
            if listing.get("sample_url") else
            "I can have a sample cut for this exact property within days. "
        ),
        "active_listings": agent.get("active_listings"),
        "callback_note": "",
    }
    missing = [t for t, v in tokens.items() if v in (None, "")]
    if "listing_address" in missing:
        # address is REQUIRED to name a real property; without it we do not call.
        raise ValueError("NEEDS_REVIEW: listing_address missing - cannot render honest script")
    text = PRIMARY_TEMPLATE.format(
        agent_name=tokens["agent_name"] or "[NEEDS_REVIEW:agent_name]",
        operator=operator,
        listing_address=tokens["listing_address"],
        brokerage_clause=tokens["brokerage_clause"],
        sample_clause=tokens["sample_clause"],
    )
    return text


def objection_branch(key: str) -> str:
    try:
        return OBJECTION_BRANCHES[key]
    except KeyError:
        return f"[NEEDS_REVIEW:unknown_objection:{key}]"


def validate_no_fabrication(rendered: str) -> bool:
    """A rendered script must not contain invented-number markers."""
    return "[NEEDS_REVIEW" not in re.sub(r"\{[a-z_]+\}", "", rendered)
