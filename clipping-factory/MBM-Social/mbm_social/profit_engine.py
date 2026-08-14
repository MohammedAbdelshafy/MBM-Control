"""
profit_engine -- YouTube US-view monetization + fast-profit ranking (jarvis-mbm #18).

Measurable pieces:
  - US_AUDIENCE_SCORE: computed ONLY from reported Analytics geography data
    (us view share, us watch-time share, returning-viewer, subscriber
    conversion, retention, publish-window fit, language/topic fit).
  - MONETIZATION_RISK_SCORE: pre-publish rights/reuse risk gate. Hard-blocks
    assets that are likely reused-content / mass-produced / inauthentic.
  - fast-profit ranking: expected_verified_net_value / production_minute with
    confidence and downside risk; cash-realizable beats speculative YPP.

HONESTY: every number is labelled expected (estimate) or verified (reported).
No geography spoofing; US share is measured, never guaranteed.
"""
from __future__ import annotations

import json
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


class ProfitEngineError(Exception):
    """Raised when an input violates the honesty contract."""


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# US audience score (measured, from Analytics-reported values)
# --------------------------------------------------------------------------

@dataclass
class USAudienceInput:
    us_view_share: Optional[float] = None      # 0-1 fraction of views from US
    us_watch_time_share: Optional[float] = None  # 0-1 fraction of watch time from US
    us_returning_viewer_share: Optional[float] = None  # 0-1
    us_subscriber_conversion: Optional[float] = None   # 0-1
    retention: Optional[float] = None          # 0-1 average view duration share
    publish_window_fit: float = 0.5     # 0-1 fit to US time zones
    language_topic_fit: float = 0.5     # 0-1 english/US-metadata fit


US_AUDIENCE_WEIGHTS = {
    "us_view_share": 0.30,
    "us_watch_time_share": 0.20,
    "us_returning_viewer_share": 0.10,
    "us_subscriber_conversion": 0.10,
    "retention": 0.10,
    "publish_window_fit": 0.10,
    "language_topic_fit": 0.10,
}


def us_audience_score(inp: USAudienceInput) -> dict:
    """
    Weighted 0-100 score. Missing Analytics fields score 0 (measured only);
    the score is never inflated by guessing geography. Unknown => low.
    """
    def _pct(v: Optional[float]) -> float:
        if v is None:
            return 0.0
        if not 0.0 <= v <= 1.0:
            raise ProfitEngineError(f"share out of range: {v}")
        return float(v) * 100.0

    for name, weight in US_AUDIENCE_WEIGHTS.items():
        if name in ("publish_window_fit", "language_topic_fit"):
            if not 0.0 <= getattr(inp, name) <= 1.0:
                raise ProfitEngineError(f"{name} out of range")
            continue

    components = {
        "us_view_share": _pct(inp.us_view_share),
        "us_watch_time_share": _pct(inp.us_watch_time_share),
        "us_returning_viewer_share": _pct(inp.us_returning_viewer_share),
        "us_subscriber_conversion": _pct(inp.us_subscriber_conversion),
        "retention": _pct(inp.retention),
        "publish_window_fit": inp.publish_window_fit * 100.0,
        "language_topic_fit": inp.language_topic_fit * 100.0,
    }
    score = sum(US_AUDIENCE_WEIGHTS[k] * components[k] for k in US_AUDIENCE_WEIGHTS)
    measured_keys = (
        "us_view_share", "us_watch_time_share", "us_returning_viewer_share",
        "us_subscriber_conversion", "retention",
    )
    measured = sum(1 for k in measured_keys if getattr(inp, k) is not None)
    return {
        "score": round(score, 1),
        "components": components,
        "measured_analytics_dimensions": measured,
        "note": (
            "score reflects measured Analytics geography data only; "
            "no location spoofing or geo manipulation."
        ),
    }


def us_audience_score_from_row(row: dict) -> dict:
    """Build the score from an analytics ledger row (reported_* fields)."""
    a = row.get("analytics", {})
    return us_audience_score(
        USAudienceInput(
            us_view_share=a.get("reported_us_view_share"),
            us_watch_time_share=a.get("reported_us_watch_time_share"),
            us_returning_viewer_share=a.get("reported_us_returning_viewer_share"),
            us_subscriber_conversion=a.get("reported_us_subscriber_conversion"),
            retention=a.get("reported_retention"),
            publish_window_fit=float(a.get("publish_window_fit", 0.5)),
            language_topic_fit=float(a.get("language_topic_fit", 0.5)),
        )
    )


# --------------------------------------------------------------------------
# Monetization risk / rights gate
# --------------------------------------------------------------------------

MONETIZATION_RISK_RULES = {
    "reused_verbatim_source": {
        "points": 40,
        "reason": "verbatim reuse of source without transformation",
    },
    "no_original_commentary": {"points": 25, "reason": "no original narration/commentary"},
    "no_editorial_framing": {"points": 20, "reason": "no editorial framing/storyline"},
    "no_source_attribution": {"points": 15, "reason": "source attribution missing"},
    "mass_produced_identical": {"points": 30, "reason": "mass-produced/identical template output"},
    "inauthentic_engagement": {"points": 50, "reason": "artificial/inauthentic engagement risk"},
    "rights_unclear": {"points": 20, "reason": "rights/permission state unclear"},
}

HARD_BLOCK_THRESHOLD = 70


@dataclass
class MonetizationRiskInput:
    reused_verbatim_source: bool = False
    no_original_commentary: bool = False
    no_editorial_framing: bool = False
    no_source_attribution: bool = False
    mass_produced_identical: bool = False
    inauthentic_engagement: bool = False
    rights_unclear: bool = False


def monetization_risk_score(inp: MonetizationRiskInput) -> dict:
    """
    Pre-publish rights/reuse gate (0-100). Hard-block when >= 70.
    Used to refuse publishing inauthentic/reused content, per YPP policy.
    """
    total = 0
    reasons: list[str] = []
    for rule, meta in MONETIZATION_RISK_RULES.items():
        if getattr(inp, rule):
            total += meta["points"]
            reasons.append(meta["reason"])
    score = min(total, 100)
    return {
        "score": score,
        "blocked": score >= HARD_BLOCK_THRESHOLD,
        "reasons": reasons,
        "note": (
            "hard-blocked assets are NOT published until rights/transformative "
            "requirements are met (YPP monetization policy)."
        ),
    }


def monetization_risk_score_from_row(row: dict) -> dict:
    """Build the gate from a row's risk flags (defaults safe: False)."""
    a = row.get("analytics", {})
    return monetization_risk_score(
        MonetizationRiskInput(
            reused_verbatim_source=bool(a.get("risk_reused_verbatim_source")),
            no_original_commentary=bool(a.get("risk_no_original_commentary")),
            no_editorial_framing=bool(a.get("risk_no_editorial_framing")),
            no_source_attribution=bool(a.get("risk_no_source_attribution")),
            mass_produced_identical=bool(a.get("risk_mass_produced_identical")),
            inauthentic_engagement=bool(a.get("risk_inauthentic_engagement")),
            rights_unclear=bool(a.get("risk_rights_unclear")),
        )
    )


# --------------------------------------------------------------------------
# Fast-profit ranking
# --------------------------------------------------------------------------

@dataclass
class ProfitOpportunity:
    opportunity_id: str
    revenue_path: str  # content_rewards | direct_client | affiliate | lead_product | automation
    expected_net_value_usd: float
    production_minutes: float
    confidence: float
    downside_risk: float  # 0-1
    cash_realizable: bool = True  # True = cash today; False = speculative (YPP)
    source: str = "estimate"


def profit_per_minute(opp: ProfitOpportunity) -> float:
    if opp.expected_net_value_usd < 0:
        raise ProfitEngineError(f"{opp.opportunity_id}: negative expected value")
    if not 0.0 <= opp.confidence <= 1.0:
        raise ProfitEngineError(f"{opp.opportunity_id}: confidence out of range")
    if not 0.0 <= opp.downside_risk <= 1.0:
        raise ProfitEngineError(f"{opp.opportunity_id}: risk out of range")
    if opp.production_minutes <= 0:
        raise ProfitEngineError(f"{opp.opportunity_id}: production_minutes must be > 0")
    per_minute = opp.expected_net_value_usd / opp.production_minutes
    return round(per_minute * opp.confidence * (1.0 - opp.downside_risk), 4)


def rank_profit(opportunities: list[ProfitOpportunity], top_n: int = 5) -> list[dict]:
    """Rank by expected_verified_net_value / production_minute (cash-first)."""
    ranked = []
    for opp in opportunities:
        pm = profit_per_minute(opp)
        ranked.append(
            {
                "opportunity_id": opp.opportunity_id,
                "revenue_path": opp.revenue_path,
                "expected_net_value_usd": opp.expected_net_value_usd,
                "expected_basis": opp.source,
                "production_minutes": opp.production_minutes,
                "confidence": opp.confidence,
                "downside_risk": opp.downside_risk,
                "cash_realizable": opp.cash_realizable,
                "net_per_minute_usd": pm,
            }
        )
    # cash-realizable first, then net/min desc, then id asc (deterministic).
    ranked.sort(key=lambda r: (not r["cash_realizable"], -r["net_per_minute_usd"], r["opportunity_id"]))
    return ranked[:top_n]


def profit_dashboard(opportunities: list[ProfitOpportunity], top_n: int = 5) -> dict:
    """7-day profit sprint view: cash vs speculative separated."""
    ranked = rank_profit(opportunities, top_n=top_n)
    cash = [r for r in ranked if r["cash_realizable"]]
    speculative = [r for r in ranked if not r["cash_realizable"]]
    total_cash_value = round(sum(r["expected_net_value_usd"] for r in cash), 2)
    return {
        "generated_at": _iso_now(),
        "cash_realizable_pipeline": cash,
        "speculative_platform_revenue": speculative,
        "total_expected_cash_value_usd": total_cash_value,
        "note": "every number is an EXPECTED estimate; verified values live in the revenue ledger.",
        "next_action": (
            cash[0]["opportunity_id"] if cash
            else "no cash-realizable opportunity; validate a content_rewards/direct-client path first"
        ),
    }


def main(argv: Optional[list[str]] = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Profit engine (US audience + risk + fast profit)")
    parser.add_argument("--demo", action="store_true", help="run a deterministic demo")
    args = parser.parse_args(argv)
    if not args.demo:
        parser.print_help()
        return 0
    inp = USAudienceInput(us_view_share=0.55, us_watch_time_share=0.5, retention=0.6)
    print(json.dumps(us_audience_score(inp), indent=2))
    risk = MonetizationRiskInput(reused_verbatim_source=True, no_original_commentary=True)
    print(json.dumps(monetization_risk_score(risk), indent=2))
    opps = [
        ProfitOpportunity("cc-1", "content_rewards", 45.0, 15.0, 0.8, 0.1, True),
        ProfitOpportunity("direct-1", "direct_client", 120.0, 30.0, 0.6, 0.2, True),
        ProfitOpportunity("ypp-1", "content_rewards", 100.0, 20.0, 0.3, 0.5, False),
    ]
    print(json.dumps(profit_dashboard(opps), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())