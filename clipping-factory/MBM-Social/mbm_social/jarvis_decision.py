"""
jarvis_decision -- JARVIS capacity-aware next-action ranking (issue #18).

Ranks candidate work by expected verified value, confidence, risk and available
capacity, and emits ONE deterministic next_action. This is NOT a second
orchestrator: it is a pure decision function fed by lineage + economics events.

Honesty contract (matches fleet invariants):
- expected value is ALWAYS labelled expected; never mixed with verified figures.
- missing/unknown inputs lower the score instead of being invented.
- capacity is hard: an item whose required capacity exceeds the budget is
  skipped, never truncated.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from .routing import RoutingError, resolve_destination


class JarvisDecisionError(Exception):
    """Raised when a decision input is invalid (fails closed)."""


@dataclass
class Candidate:
    candidate_id: str
    brand_id: str
    target_platform: str
    expected_net_revenue_usd: float
    confidence: float
    risk: float
    production_minutes: float
    source: str = "unknown"
    asset_id: str = ""

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def score_candidate(candidate: Candidate) -> float:
    """
    JARVIS expected-value score (0..1 scale, higher = better).

    score = expected_net * confidence * (1 - risk), normalized by a $25/hr
    reference floor so low-value work cannot outrank higher-value work.
    Fails closed: negative revenue or out-of-range confidence/risk => raise.
    """
    if candidate.expected_net_revenue_usd < 0:
        raise JarvisDecisionError(
            f"candidate {candidate.candidate_id}: expected revenue cannot be negative"
        )
    if not 0.0 <= candidate.confidence <= 1.0:
        raise JarvisDecisionError(
            f"candidate {candidate.candidate_id}: confidence {candidate.confidence} out of range"
        )
    if not 0.0 <= candidate.risk <= 1.0:
        raise JarvisDecisionError(
            f"candidate {candidate.candidate_id}: risk {candidate.risk} out of range"
        )
    per_minute = candidate.expected_net_revenue_usd / max(candidate.production_minutes, 0.5)
    reference = 25.0 / 60.0  # $25/hr reference floor
    normalized = max(min(per_minute / reference, 5.0), 0.0) / 5.0
    return round(normalized * candidate.confidence * (1.0 - candidate.risk), 6)


def resolve_destination_for(candidate: Candidate) -> dict:
    """
    Resolve the canonical destination for a candidate. Fails closed: a candidate
    that cannot be routed cannot be selected (issue #16 invariant).
    """
    pkg = {
        "brand": candidate.brand_id,
        "target_platform": candidate.target_platform,
        "asset_id": candidate.asset_id or candidate.candidate_id,
    }
    dest = resolve_destination(pkg)
    return {
        "asset_id": dest.asset_id,
        "brand_id": dest.brand_id,
        "account_id": dest.account_id,
        "platform": dest.platform,
        "channel": dest.channel,
        "publish_enabled": dest.publish_enabled,
    }


def rank_candidates(
    candidates: list[Candidate],
    *,
    daily_production_minutes: float,
    max_actions: int = 3,
) -> list[dict]:
    """
    Rank candidates by JARVIS score within the production budget.

    Deterministic: score desc, then candidate_id asc as tie-break. The output is
    a ranked plan of dicts, each with score, expected/verified separation, and
    the resolved destination (fails closed on unroutable candidates).
    """
    scored = []
    for cand in candidates:
        score = score_candidate(cand)
        try:
            dest = resolve_destination_for(cand)
        except RoutingError as e:
            scored.append(
                {
                    "candidate_id": cand.candidate_id,
                    "score": score,
                    "status": "UNROUTABLE",
                    "reason": str(e),
                }
            )
            continue
        scored.append(
            {
                "candidate_id": cand.candidate_id,
                "brand_id": cand.brand_id,
                "asset_id": dest["asset_id"],
                "account_id": dest["account_id"],
                "platform": dest["platform"],
                "channel": dest["channel"],
                "score": score,
                "confidence": cand.confidence,
                "risk": cand.risk,
                "expected_net_revenue_usd": cand.expected_net_revenue_usd,
                "expected_basis": "estimate",
                "production_minutes": cand.production_minutes,
                "publish_enabled": dest["publish_enabled"],
                "status": "SELECTED",
            }
        )

    selected = [r for r in scored if r["status"] == "SELECTED" and r["publish_enabled"]]
    selected.sort(key=lambda r: (-r["score"], r["candidate_id"]))

    budget_remaining = max(float(daily_production_minutes), 0.0)
    ranked: list[dict] = []
    for row in selected:
        if budget_remaining <= 0:
            break
        minutes = max(float(row["production_minutes"]), 0.5)
        if minutes > budget_remaining:
            row["status"] = "SKIPPED_NO_CAPACITY"
            continue
        budget_remaining -= minutes
        row["rank"] = len(ranked) + 1
        ranked.append(row)
        if len(ranked) >= max_actions:
            break

    unroutable = [r for r in scored if r["status"] == "UNROUTABLE"]
    return ranked + unroutable


def make_decision(
    candidates: list[Candidate],
    *,
    daily_production_minutes: float,
    max_actions: int = 3,
    owner: str = "system",
) -> dict:
    """
    Emit the JARVIS decision output: ranked plan + single next_action.
    Matches the fleet Output Contract.
    """
    ranked = rank_candidates(
        candidates,
        daily_production_minutes=daily_production_minutes,
        max_actions=max_actions,
    )
    selected = [r for r in ranked if r["status"] == "SELECTED"]
    unselected = [r for r in ranked if r["status"] != "SELECTED"]

    next_action: str
    status = "success"
    if selected:
        top = selected[0]
        next_action = (
            f"publish {top['candidate_id']} to {top['account_id']} "
            f"({top['platform']}) on channel {top['channel']}"
        )
    elif unselected:
        status = "blocked"
        next_action = (
            "no publishable candidate; review unroutable/skipped entries "
            "(destination resolution or capacity)"
        )
    else:
        status = "skipped"
        next_action = "no candidates; waiting for pipeline output"

    decision = {
        "status": status,
        "inputs": {"daily_production_minutes": daily_production_minutes, "max_actions": max_actions},
        "outputs": {
            "ranked": ranked,
            "selected": [r["candidate_id"] for r in selected],
        },
        "errors": [r["reason"] for r in ranked if r["status"] == "UNROUTABLE"],
        "next_action": next_action,
        "owner": owner,
        "timestamp": _iso_now(),
    }
    return decision