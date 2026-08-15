"""county_registry -- property -> state -> county -> official source routing.

For a normalized property we resolve:
  1. county (explicit field, else city inference, else '')
  2. the official assessor/recorder/tax source for that county
  3. a concrete ownership adapter when the source exposes one (verified ArcGIS)

Routing never invents a county; when it cannot be determined, county stays ''
and ownership verification reports REQUIRES_VERIFICATION.
"""
from __future__ import annotations

from typing import Any, Optional

from .county_sources import best_county_source, county_sources_for
from .normalize import infer_county_from_city


def resolve_county(state: str, city: str, county: Optional[str] = None) -> str:
    """Deterministic county resolution: explicit > city-inference > ''."""
    if county and str(county).strip():
        return str(county).strip().title()
    if state and city:
        return infer_county_from_city(state, city)
    return ""


def route_property(rec: dict) -> dict:
    """Route a normalized property dict to its county + official source.

    Returns {county, county_resolved, source, routed, missing} where routed is
    True only when an official source exists for the county.
    """
    county = resolve_county(rec.get("state", ""), rec.get("city", ""), rec.get("county"))
    src = best_county_source(rec.get("state", ""), county) if county else None
    missing: list[str] = []
    if not rec.get("state"):
        missing.append("state")
    if not county:
        missing.append("county")
    if not src:
        missing.append("official_source")
    return {
        "county": county,
        "county_resolved": bool(county),
        "source": src or {},
        "routed": src is not None,
        "missing": missing,
    }


def list_counties(state: Optional[str] = None) -> list[str]:
    """Every county in the registry, optionally filtered by state."""
    st = (state or "").strip().upper()
    return sorted(
        {
            s["county"]
            for s in county_sources_for_export()
            if not st or s["state"].upper() == st
        }
    )


def county_sources_for_export() -> list[dict]:
    from .county_sources import COUNTY_SOURCES

    return COUNTY_SOURCES


def has_arcgis_adapter(state: str, county: str) -> bool:
    """True when a verified ArcGIS ownership adapter is registered for this county."""
    src = best_county_source(state, county)
    return bool(src and src.get("adapter") == "arcgis" and src.get("verified"))