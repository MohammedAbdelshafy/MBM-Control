"""Configurable opportunity scoring engine (0-100) + derived metrics.

Factors arrive normalized 0..1 from the analyzer/capability matcher; weights
come from config so the model can be tuned without code changes.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def _clamp01(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def score_opportunity(factors: Dict[str, float],
                      weights: Dict[str, int],
                      reuse_score: Optional[float] = None) -> Dict[str, Any]:
    """factors keys (0..1): demand, time_to_first_revenue (=speed), automation_potential,
    gross_margin_potential, recurring_revenue, competition_inverse, startup_cost_inverse,
    execution_ease. existing_asset_reuse may be supplied directly or via reuse_score."""
    f = {k: _clamp01(v) for k, v in factors.items()}
    if reuse_score is not None:
        f["existing_asset_reuse"] = _clamp01(reuse_score)
    total_weight = sum(int(w) for w in weights.values()) or 1
    weighted = 0.0
    per_factor = {}
    for name, weight in weights.items():
        w = int(weight)
        value = _clamp01(f.get(name, 0.5))
        per_factor[name] = {"weight": w, "value": round(value, 3),
                            "points": round(value * w, 2)}
        weighted += value * w
    score = round(weighted / total_weight * 100, 1)
    return {"opportunity_score": score, "per_factor": per_factor}


def time_to_first_revenue_days(acquisition_ready: bool, offer_defined: bool,
                               fulfillment_ready: bool) -> int:
    """Conservative estimate: selling-first needs offer+channel+fulfilment."""
    days = 1
    if not offer_defined:
        days += 1
    if not acquisition_ready:
        days += 3
    if not fulfillment_ready:
        days += 7
    return days


def estimated_build_effort_days(missing_capabilities: int, automation_pct: int) -> int:
    base = missing_capabilities * 3
    discount = 1.0 - (_clamp01(automation_pct / 100.0) * 0.5)
    return max(0, round(base * discount))


def reuse_score_from_levels(levels: Dict[str, str]) -> float:
    """HIGH=1.0 MEDIUM=0.6 LOW=0.3 NONE=0.0 averaged over known capabilities."""
    table = {"HIGH": 1.0, "MEDIUM": 0.6, "LOW": 0.3, "NONE": 0.0}
    if not levels:
        return 0.0
    vals = [table.get(v.upper(), 0.0) for v in levels.values()]
    return round(sum(vals) / len(vals), 3)
