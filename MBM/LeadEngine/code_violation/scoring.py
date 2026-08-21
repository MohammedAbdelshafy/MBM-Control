"""scoring -- code-violation lead scoring + TIER assignment.

Signal weights (mission spec, Phase 9). Score is capped at 100 and every
point carries a human-readable explanation tag. Tiers:
  TIER 1  score >= 70, verified callable phone, >= 2 distinct distress signals
  TIER 2  score >= 45, verified callable phone, >= 1 distress signal
  TIER 3  everything else (artifacts only, never auto-dialed)

Distress signals are counted from the category tags + property-level flags.
No equity / ownership-tenure data is fabricated - those signals are simply
absent when unknown.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

BASE_SCORE = 20  # being a code-violation property is itself the opportunity

SEVERITY_TAGS = ("UNSAFE", "STRUCTURAL", "PROPERTY_DERELICT", "DEMOLITION", "VACANT")

SIGNAL_WEIGHTS = [
    # (tag, weight, condition)
    ("ACTIVE", 20, lambda p: p.get("active") is True),
    ("RECENT", 15, lambda p: p.get("recent") is True),
    ("MULTIPLE", 10, lambda p: (p.get("violation_count") or 0) >= 2),
    ("REPEAT", 15, lambda p: p.get("repeat") is True),
    ("LONG_STANDING", 15, lambda p: p.get("long_standing") is True),
    ("VACANT", 20, lambda p: p.get("vacant") is True),
    ("SEVERITY", 15, lambda p: bool(set(p.get("tags") or []) & set(SEVERITY_TAGS))),
    ("ABSENTEE", 10, lambda p: p.get("absentee") is True),
    ("VERIFIED_PHONE", 10, lambda p: bool(p.get("phone"))),
    ("VERIFIED_OWNER", 5, lambda p: p.get("owner_verified") is True),
]


def distress_count(prop: dict) -> int:
    """Distinct distress signals beyond the base code-violation itself."""
    tags = set(prop.get("tags") or [])
    n = 0
    if prop.get("active"):
        n += 1
    if (prop.get("violation_count") or 0) >= 2:
        n += 1
    if prop.get("repeat"):
        n += 1
    if prop.get("long_standing"):
        n += 1
    if tags & {"VACANT", "UNSAFE", "STRUCTURAL", "PROPERTY_DERELICT", "DEMOLITION"}:
        n += 1
    if prop.get("absentee"):
        n += 1
    return n


@dataclass
class ScoreResult:
    score: int
    tags: list[str]
    tier: str
    explanation: list[str] = field(default_factory=list)


def assign_tier(score: int, phone_ok: bool, distress: int) -> str:
    if score >= 70 and phone_ok and distress >= 2:
        return "TIER 1"
    if score >= 45 and phone_ok and distress >= 1:
        return "TIER 2"
    return "TIER 3"


def score_property(prop: dict) -> ScoreResult:
    """Score one property-level code-violation lead."""
    tags: list[str] = ["CODE_VIOLATION"]
    explanation: list[str] = ["base code-violation opportunity (+20)"]
    score = BASE_SCORE
    for tag, weight, cond in SIGNAL_WEIGHTS:
        if cond(prop):
            tags.append(tag)
            score += weight
            explanation.append(f"{tag} (+{weight})")
    score = min(score, 100)
    phone_ok = bool(prop.get("phone"))
    distress = distress_count(prop)
    tier = assign_tier(score, phone_ok, distress)
    return ScoreResult(
        score=score,
        tags=tags,
        tier=tier,
        explanation=explanation,
    )


def build_property_record(
    address: str,
    city: str,
    state: str,
    county: str,
    violations: list[dict],
    owner: Optional[dict] = None,
    phone: Optional[dict] = None,
    existing: Optional[dict] = None,
) -> dict:
    """Assemble the canonical property record used for scoring + dialer sync."""
    categories = [v.get("category") for v in violations if v.get("category")]
    active = any(v.get("active") for v in violations)
    opened_days = [v.get("age_days") for v in violations if v.get("age_days") is not None]
    now_recent = 45
    recent = any(d is not None and d <= now_recent for d in opened_days)
    long_standing = active and any(d is not None and d > 90 for d in opened_days)
    types_seen = {str(v.get("violation_type") or "").strip().upper() for v in violations if v.get("violation_type")}
    repeat = len(types_seen) >= 2 or len(violations) >= 2

    prop = {
        "address": address,
        "city": city,
        "state": state,
        "county": county,
        "violation_count": len(violations),
        "active": active,
        "recent": recent,
        "long_standing": long_standing,
        "repeat": repeat,
        "vacant": bool(set(categories) & {"VACANT"}),
        "tags": sorted(set(categories) | set()),
        "violation_ids": [v.get("case_id") for v in violations],
        "sources": sorted({v.get("source") for v in violations if v.get("source")}),
        "first_opened_iso": min((v.get("opened_iso") for v in violations if v.get("opened_iso")), default=""),
        "last_opened_iso": max((v.get("opened_iso") for v in violations if v.get("opened_iso")), default=""),
        "owner_verified": False,
        "absentee": None,
        "phone": "",
    }
    if owner:
        prop["owner_name"] = owner.get("owner_name", "")
        prop["parcel_id"] = owner.get("parcel_id", "")
        prop["owner_status"] = owner.get("owner_status", "")
        prop["owner_source"] = owner.get("source", "")
        prop["owner_confidence"] = owner.get("confidence", 0.0)
        prop["owner_verified"] = owner.get("owner_status") in ("VERIFIED", "LIKELY")
        prop["absentee"] = owner.get("absentee")
    if phone:
        prop["phone"] = phone.get("phone", "")
        prop["phone_source"] = phone.get("source", "")
        prop["phone_confidence"] = phone.get("confidence", 0.0)
        prop["email"] = phone.get("email", "")
    if existing:
        prop["existing_id"] = existing.get("id")
        prop["existing_company"] = existing.get("company", "")
        prop["upgrade"] = True
    return prop
