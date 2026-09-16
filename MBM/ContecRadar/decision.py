"""Decision engine + NEXT_BEST_OPPORTUNITY ranking.

Safety: a high score NEVER auto-spends money. Experiments above the configured
budget require recorded human approval (models.Opportunity.human_approval_required).
"""
from __future__ import annotations

from typing import Any, Dict, List

from .config import load_config
from .capability_graph import match_opportunity
from .clustering import velocity
from .scoring import (estimated_build_effort_days, reuse_score_from_levels,
                      score_opportunity, time_to_first_revenue_days)
from .models import Decision, Opportunity


def enrich_and_decide(opp: Opportunity, config: Dict[str, Any] | None = None) -> Opportunity:
    cfg = config or load_config()
    weights = cfg["weights"]
    thresholds = cfg["decision_thresholds"]
    text = " ".join(filter(None, [opp.title] +
                           [c.product_service + " " + c.target_customer for c in opp.cards]))
    match = match_opportunity(text)
    opp.reuse_scores = match["reuse_scores"]

    reuse = reuse_score_from_levels(opp.reuse_scores)
    top_price = max([c.claimed_price_usd or 0 for c in opp.cards] or [0])
    recurring = any(c.recurring_revenue for c in opp.cards)
    automation = max([c.automation_potential for c in opp.cards] or [50])

    factors = {
        # demand: signals + source diversity (capped)
        "demand": min(1.0, 0.25 * opp.signal_count + 0.15 * len(opp.sources_seen)),
        # speed to revenue: offer+price evidence already visible => fast
        "time_to_first_revenue": 0.9 if top_price >= 200 else 0.6 if top_price > 0 else 0.3,
        "automation_potential": automation / 100.0,
        "gross_margin_potential": 0.85 if automation >= 70 else 0.55,
        "recurring_revenue": 1.0 if recurring else 0.35,
        # competition unknown from one reel: neutral-ish, slightly penalized when saturated
        "competition_inverse": 0.7,
        "startup_cost_inverse": 0.9 if automation >= 70 else 0.6,
        "execution_ease": 0.75,
    }
    result = score_opportunity(factors, weights, reuse_score=reuse)
    opp.score = result["opportunity_score"]
    vel = velocity(opp)

    if vel.value == "saturated":
        decision = Decision.ARCHIVE
    elif opp.score >= thresholds["build_now"]:
        decision = Decision.BUILD_NOW
    elif opp.score >= thresholds["experiment"]:
        decision = Decision.EXPERIMENT
    else:
        decision = Decision.WATCH
    opp.decision = decision.value

    top_card = max(opp.cards, key=lambda c: c.operational_complexity) if opp.cards else None
    opp.time_to_first_revenue_days = time_to_first_revenue_days(
        acquisition_ready=bool(opp.reuse_scores.get("dialer")),
        offer_defined=top_price > 0,
        fulfillment_ready=automation >= 70)
    opp.build_effort_days = estimated_build_effort_days(
        missing_capabilities=len(match["missing_capabilities"]),
        automation_pct=automation)
    opp.estimated_monthly_revenue_usd = round(top_price * (4 if recurring else 2), 2)
    opp.human_approval_required = True   # conservative default; spend gates below
    return opp


def next_best_opportunities(opportunities: List[Opportunity],
                            config: Dict[str, Any] | None = None,
                            limit: int = 5) -> List[Opportunity]:
    """Rank by score with velocity bonus and active-experiment penalty."""
    cfg = config or load_config()
    def rank(o: Opportunity) -> float:
        bonus = {"accelerating": 6, "emerging": 4, "stable": 0,
                 "declining": -4, "saturated": -10}.get(o.velocity, 0)
        active_penalty = 8 if o.decision in ("BUILD_NOW", "EXPERIMENT") and any(
            e.get("status") in ("approved", "running") for e in o.history) else 0
        return o.score + bonus - active_penalty
    ranked = sorted(opportunities, key=rank, reverse=True)
    return ranked[:limit]


def requires_human_approval(opp: Opportunity, planned_spend_usd: float,
                            config: Dict[str, Any] | None = None) -> bool:
    cfg = config or load_config()
    if planned_spend_usd <= float(cfg["max_auto_experiment_budget_usd"]):
        return False
    return True
