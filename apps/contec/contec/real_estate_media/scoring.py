"""REAL_ESTATE_MEDIA_SCORE - evidence-weighted qualification.

Law: every point traces to a named signal; missing evidence contributes zero
and is reported as UNKNOWN factors. Never guessed (D-019 rail 16).
"""
from __future__ import annotations

from typing import Any, Dict, List, Tuple

WEIGHTS: List[Tuple[str, int]] = [
    ("active_listings", 25),
    ("listing_volume_90d", 15),
    ("presentation_quality", 15),
    ("existing_video_usage_gap", 10),   # has listings but poor/no video -> opportunity
    ("social_presence", 10),
    ("brokerage_size", 10),
    ("market_value_tier", 10),
    ("recurring_demand_signal", 5),
]
MAX_SCORE = sum(w for _, w in WEIGHTS)


def _as_int(v: Any, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def _tier_score(median_price: Any) -> int:
    try:
        p = float(median_price)
    except (TypeError, ValueError):
        return 0
    if p <= 0:
        return 0
    if p >= 1_000_000:
        return 10
    if p >= 500_000:
        return 7
    if p >= 250_000:
        return 4
    return 2


def real_estate_media_score(agent: Dict[str, Any]) -> Dict[str, Any]:
    """Return {score, tier, evidence[], unknown_factors[]} - traceable."""
    evidence: List[Dict[str, Any]] = []
    unknown: List[str] = []
    score = 0

    active = _as_int(agent.get("active_listings"))
    if active > 0:
        pts = WEIGHTS[0][1] if active >= 3 else max(5, active * 5)
        score += pts
        evidence.append({"signal": "active_listings", "value": active, "points": pts})
    else:
        unknown.append("active_listings")

    vol90 = _as_int(agent.get("listings_last_90d"))
    if vol90 > 0:
        pts = min(WEIGHTS[1][1], vol90 * 3)
        score += pts
        evidence.append({"signal": "listing_volume_90d", "value": vol90, "points": pts})
    else:
        unknown.append("listing_volume_90d")

    pq = str(agent.get("presentation_quality") or "").upper()
    pq_map = {"POOR": 15, "MIXED": 10, "GOOD": 6, "PROFESSIONAL": 3}
    if pq in pq_map:
        pts = pq_map[pq]
        score += pts
        evidence.append({"signal": "presentation_quality", "value": pq, "points": pts})
    else:
        unknown.append("presentation_quality")

    if active > 0 and pq in ("POOR", "MIXED", "", ) or (active > 0 and not agent.get("has_video")):
        pts = WEIGHTS[3][1] if active > 0 else 0
        if pts:
            score += pts
            evidence.append({"signal": "existing_video_usage_gap", "points": pts})

    social = _as_int(agent.get("social_followers"))
    if social >= 1000:
        pts = WEIGHTS[4][1] if social >= 10000 else 5
        score += pts
        evidence.append({"signal": "social_presence", "value": social, "points": pts})
    elif social == 0 and agent.get("social_url"):
        unknown.append("social_followers")

    agents_brokerage = _as_int(agent.get("brokerage_agent_count"))
    if agents_brokerage > 0:
        pts = WEIGHTS[5][1] if agents_brokerage >= 50 else (6 if agents_brokerage >= 10 else 3)
        score += pts
        evidence.append({"signal": "brokerage_size", "value": agents_brokerage, "points": pts})
    else:
        unknown.append("brokerage_size")

    tier_pts = _tier_score(agent.get("market_median_price"))
    if tier_pts:
        score += tier_pts
        evidence.append({"signal": "market_value_tier",
                         "value": agent.get("market_median_price"), "points": tier_pts})
    else:
        unknown.append("market_value_tier")

    if agent.get("repeat_client_signal") or agent.get("high_turnover_market"):
        score += WEIGHTS[7][1]
        evidence.append({"signal": "recurring_demand_signal", "points": WEIGHTS[7][1]})

    score = min(MAX_SCORE, score)
    tier = "A" if score >= 70 else ("B" if score >= 45 else ("C" if score >= 20 else "D"))
    return {"score": score, "max": MAX_SCORE, "tier": tier,
            "evidence": evidence, "unknown_factors": unknown}
