"""
revenue_attribution -- Per-clip and per-campaign economics (Phase 7).

CRITICAL HONESTY RULES (same as content_rewards):
  - ESTIMATED revenue is a projection (model/RPM prior). Always labelled.
  - ACTUAL revenue is settled money from a verification source. Never invented.
  - Reward rates are CONFIGURABLE and must be verified against the official
    program/platform source before use. Defaults are placeholders flagged
    `verified=False`.

This module computes revenue-per-1K / per-1M views, cost-per-clip, campaign profit
and ROI from a set of clip results, keeping estimated and actual strictly apart.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class RewardRate:
    platform: str
    rpm_usd: float  # revenue per mille (1000 views), USD
    verified: bool = False
    source: str = "PLACEHOLDER — verify against official program"
    as_of: str = ""


class RewardRateRegistry:
    """Configurable RPM rates per platform. Defaults are UNVERIFIED placeholders."""

    def __init__(self, rates: Optional[dict[str, RewardRate]] = None) -> None:
        self._rates: dict[str, RewardRate] = rates or {
            "youtube": RewardRate("youtube", 3.0, verified=False, source="YouTube Partner Program RPM (verify)"),
            "tiktok": RewardRate("tiktok", 0.0, verified=False, source="TikTok Creator Rewards (verify eligibility)"),
            "instagram": RewardRate("instagram", 0.0, verified=False, source="Instagram Bonus (invite-only, verify)"),
            "linkedin": RewardRate("linkedin", 0.0, verified=False, source="No native RPM program"),
            "twitter": RewardRate("twitter", 0.0, verified=False, source="X Ads / Amplify (verify)"),
        }

    def set(self, platform: str, rpm_usd: float, *, verified: bool = False,
            source: str = "", as_of: str = "") -> None:
        self._rates[platform] = RewardRate(platform, float(rpm_usd),
                                           verified=verified, source=source, as_of=as_of)

    def rate(self, platform: str) -> RewardRate:
        return self._rates.get(platform, RewardRate(platform, 0.0, verified=False))


@dataclass
class ClipEconomics:
    clip_id: str
    platform: str
    views: float
    cost_usd: float
    # exactly one of (estimated_revenue_usd, actual_revenue_usd) should be set
    estimated_revenue_usd: float = 0.0
    actual_revenue_usd: float = 0.0
    is_actual: bool = False

    @property
    def revenue_usd(self) -> float:
        return self.actual_revenue_usd if self.is_actual else self.estimated_revenue_usd

    @property
    def revenue_per_1k(self) -> float:
        return (self.revenue_usd / self.views * 1000.0) if self.views else 0.0

    @property
    def revenue_per_1m(self) -> float:
        return (self.revenue_usd / self.views * 1_000_000.0) if self.views else 0.0

    @property
    def profit_usd(self) -> float:
        return self.revenue_usd - self.cost_usd

    @property
    def roi(self) -> float:
        return (self.profit_usd / self.cost_usd) if self.cost_usd else 0.0


def estimate_clip(clip_id: str, platform: str, views: float, cost_usd: float,
                  registry: RewardRateRegistry) -> ClipEconomics:
    rate = registry.rate(platform)
    est = (views / 1000.0) * rate.rpm_usd
    return ClipEconomics(clip_id=clip_id, platform=platform, views=views, cost_usd=cost_usd,
                         estimated_revenue_usd=round(est, 4), is_actual=False)


def actual_clip(clip_id: str, platform: str, views: float, cost_usd: float,
                revenue_usd: float) -> ClipEconomics:
    return ClipEconomics(clip_id=clip_id, platform=platform, views=views, cost_usd=cost_usd,
                         actual_revenue_usd=round(revenue_usd, 4), is_actual=True)


@dataclass
class CampaignProfit:
    clips: int
    total_views: float
    total_cost_usd: float
    estimated_revenue_usd: float
    actual_revenue_usd: float
    revenue_per_1k: float
    revenue_per_1m: float
    cost_per_clip: float
    profit_usd: float
    roi: float
    has_actual: bool


def campaign_profit(rows: list[ClipEconomics]) -> CampaignProfit:
    if not rows:
        return CampaignProfit(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, False)
    views = sum(r.views for r in rows)
    cost = sum(r.cost_usd for r in rows)
    est = sum(r.estimated_revenue_usd for r in rows)
    act = sum(r.actual_revenue_usd for r in rows)
    has_actual = any(r.is_actual for r in rows)
    rev = act if has_actual else est
    per1k = (rev / views * 1000.0) if views else 0.0
    per1m = (rev / views * 1_000_000.0) if views else 0.0
    cpc = (cost / len(rows)) if rows else 0.0
    profit = rev - cost
    roi = (profit / cost) if cost else 0.0
    return CampaignProfit(
        clips=len(rows), total_views=views, total_cost_usd=round(cost, 4),
        estimated_revenue_usd=round(est, 4), actual_revenue_usd=round(act, 4),
        revenue_per_1k=round(per1k, 4), revenue_per_1m=round(per1m, 4),
        cost_per_clip=round(cpc, 4), profit_usd=round(profit, 4), roi=round(roi, 4),
        has_actual=has_actual,
    )
