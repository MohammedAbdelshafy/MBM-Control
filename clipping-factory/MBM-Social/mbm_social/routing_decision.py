"""
routing_decision -- Multi-brand/multi-channel routing decision (Phase 4).

Answers the four questions for every candidate:
  WHERE  -> canonical account/channel (routing.resolve_destination, fails closed)
  WHEN   -> next open posting window (brand posting windows)
  SHOULD -> quality + daily caps (distribution_optimizer)
  WHICH  -> A/B variant selection via experiment_rate

Reuses existing `routing`, `platform_registry`, `brand_config`, and
`distribution_optimizer`. Never invents a destination; if routing cannot resolve,
the clip is flagged MANUAL for a human.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any, Optional

from . import routing
from . import platform_registry as pr
from . import brand_config as bc
from . import distribution_optimizer as dist
from .candidate_pool import Candidate


@dataclass
class RoutingDecision:
    clip_id: str
    platform: str
    channel: str = ""
    account_id: str = ""
    publish_at: str = ""
    should_publish: bool = False
    variant: str = "A"
    manual: bool = False
    reasons: list[str] = field(default_factory=list)


def _next_window(brand_slug: str) -> str:
    try:
        brand = bc.load_brand(brand_slug)
        posting = brand.get("posting", {})
        return publish_package_next_window(posting)
    except Exception:
        return publish_package_next_window({})


def publish_package_next_window(posting: dict) -> str:
    # local import to avoid circulars at module load
    from . import publish_package as pp
    return pp._next_window(posting)


def decide(candidate: Candidate, brand_slug: str, policy: dist.DistributionPolicy,
           used_per_platform: Optional[dict[str, int]] = None,
           used_per_channel: Optional[dict[str, int]] = None,
           experiment_seed: Optional[float] = None) -> RoutingDecision:
    used_per_platform = used_per_platform or {}
    used_per_channel = used_per_channel or {}
    scores = candidate.scores
    reasons: list[str] = []

    # WHERE: platform from recommendation, but never a blocked one
    platform = candidate.recommended_platform
    try:
        pr.assert_publishable(platform)
    except KeyError:
        reasons.append(f"{platform} blocked -> cannot auto-publish")
        return RoutingDecision(candidate.clip_id, platform, manual=True, reasons=reasons)

    # channel resolution (fails closed -> manual)
    channel = account_id = ""
    try:
        dest = routing.resolve_destination({
            "brand": brand_slug, "target_platform": platform,
            "asset_id": candidate.clip_id,
        })
        channel = dest.channel
        account_id = dest.account_id
    except Exception as e:
        reasons.append(f"routing unresolved ({e}) -> manual")
        return RoutingDecision(candidate.clip_id, platform, manual=True,
                               should_publish=False, reasons=reasons)

    # WHEN
    publish_at = _next_window(brand_slug)

    # SHOULD: quality gate + daily caps
    should = (
        scores["overall_score"] >= policy.min_quality_score
        and scores["hook_score"] >= policy.min_hook_score
        and scores["retention_prediction"] >= policy.min_predicted_retention
        and dist.within_daily_caps(used_per_platform, used_per_channel, platform, channel, policy)
    )
    if not should:
        reasons.append("quality or daily-cap gate not met")

    # WHICH variant
    seed = experiment_seed if experiment_seed is not None else random.random()
    variant = "B" if seed < policy.experiment_rate else "A"

    return RoutingDecision(
        clip_id=candidate.clip_id, platform=platform, channel=channel,
        account_id=account_id, publish_at=publish_at, should_publish=should,
        variant=variant, manual=False, reasons=reasons,
    )
