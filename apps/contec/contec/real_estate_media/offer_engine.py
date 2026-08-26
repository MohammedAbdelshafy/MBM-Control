"""Offer engine - configurable packages (NO hard-coded prices).

Package catalog lives in RE Media Settings (JSON config). Recommendation rules
are pure functions of agent evidence; operators may always override.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

DEFAULT_CATALOG: List[Dict[str, Any]] = [
    {"code": "SINGLE_PROPERTY", "label": "Single-Property Package",
     "unit": "per_property", "price": None},
    {"code": "MULTI_PROPERTY", "label": "Multi-Property Package",
     "unit": "bundle", "price": None, "min_listings": 3},
    {"code": "MONTHLY_SUBSCRIPTION", "label": "Monthly Content Subscription",
     "unit": "monthly", "price": None},
    {"code": "BROKERAGE_PACKAGE", "label": "Brokerage Package",
     "unit": "brokerage", "price": None, "min_brokerage_agents": 20},
    {"code": "CUSTOM_QUOTE", "label": "Custom Quote", "unit": "quote", "price": None},
]


def catalog(settings: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    if settings and settings.get("package_catalog"):
        return settings["package_catalog"]
    return [dict(p) for p in DEFAULT_CATALOG]


def recommend(agent: Dict[str, Any], score: Dict[str, Any],
              history: Optional[List[str]] = None,
              settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Recommend a package code from evidence. Pure; override-able."""
    history = history or []
    active = int(agent.get("active_listings") or 0)
    brokerage_agents = int(agent.get("brokerage_agent_count") or 0)
    is_brokerage_contact = bool(agent.get("is_brokerage_decision_maker"))

    if "MONTHLY_SUBSCRIPTION" in history:
        rec = "MULTI_PROPERTY"
        why = "Existing subscriber expanding inventory"
    elif is_brokerage_contact and brokerage_agents >= 20 and score["tier"] in ("A", "B"):
        rec = "BROKERAGE_PACKAGE"
        why = f"Brokerage-level contact at {brokerage_agents}-agent firm"
    elif active >= 5 or score["tier"] == "A":
        rec = "MONTHLY_SUBSCRIPTION"
        why = f"{active} active listings + tier-{score['tier']} fit => recurring demand"
    elif active >= 3:
        rec = "MULTI_PROPERTY"
        why = f"{active} active listings justify bundle economics"
    elif active >= 1:
        rec = "SINGLE_PROPERTY"
        why = "Start with strongest active listing as paid pilot"
    else:
        rec = None
        why = "No active inventory - nurture only, do not quote"

    return {
        "recommended": rec,
        "why": why,
        "override_allowed": True,
        "catalog": catalog(settings),
    }
