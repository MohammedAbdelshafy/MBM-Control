"""
distribution_optimizer -- High-volume distribution controls + auto-scaling (Phase 5).

Holds the campaign-level knobs the brief requires:

    target_candidates_per_source
    target_publishable_clips_per_source
    max_daily_publishes_per_channel
    max_daily_publishes_per_platform
    queue_capacity
    min_quality_score
    min_hook_score
    min_predicted_retention
    min_predicted_ctr
    experiment_rate

and decides, from recent performance, how to scale volume up or down and how to
allocate it across platforms. Pure math — no I/O — so it is fully testable.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DistributionPolicy:
    target_candidates_per_source: int = 50
    target_publishable_clips_per_source: int = 10
    max_daily_publishes_per_channel: int = 5
    max_daily_publishes_per_platform: int = 20
    queue_capacity: int = 200
    min_quality_score: float = 0.45
    min_hook_score: float = 0.40
    min_predicted_retention: float = 0.40
    min_predicted_ctr: float = 0.03
    experiment_rate: float = 0.10  # fraction of clips that try a different variant

    def __post_init__(self) -> None:
        # clamp experiment_rate to [0,1]
        self.experiment_rate = max(0.0, min(1.0, self.experiment_rate))


@dataclass
class PerformanceSignal:
    avg_quality: float = 0.5
    avg_retention: float = 0.5
    avg_ctr: float = 0.03
    publish_success_rate: float = 1.0
    trend: str = "flat"  # up | flat | down


def within_daily_caps(used_per_platform: dict[str, int], used_per_channel: dict[str, int],
                      platform: str, channel: str, policy: DistributionPolicy) -> bool:
    if used_per_platform.get(platform, 0) >= policy.max_daily_publishes_per_platform:
        return False
    if used_per_channel.get(channel, 0) >= policy.max_daily_publishes_per_channel:
        return False
    return True


def recommend(policy: DistributionPolicy, perf: Optional[PerformanceSignal] = None,
              queue_depth: int = 0) -> dict:
    """Compute scaling + allocation decisions from recent performance."""
    perf = perf or PerformanceSignal()
    scale = 1.0
    actions: list[str] = []

    if perf.trend == "up" and perf.avg_quality >= policy.min_quality_score:
        scale = 1.25
        actions.append("performance up -> increase volume 25%")
    elif perf.trend == "down" or perf.avg_quality < policy.min_quality_score:
        scale = 0.6
        actions.append("performance down -> reduce volume 40%")
        actions.append("rotate hooks / sources / platform allocation")
    else:
        actions.append("hold volume")

    target_candidates = int(round(policy.target_candidates_per_source * scale))
    target_publishable = int(round(policy.target_publishable_clips_per_source * scale))

    # queue backpressure: never plan more than capacity allows
    headroom = max(0, policy.queue_capacity - queue_depth)
    if target_publishable > headroom:
        target_publishable = headroom
        actions.append("queue at capacity -> cap publishable plan to headroom")

    # platform allocation weights shift toward better performers
    if perf.trend == "up":
        allocation = {"youtube": 0.4, "tiktok": 0.3, "instagram": 0.2, "linkedin": 0.05, "twitter": 0.05}
    elif perf.trend == "down":
        allocation = {"youtube": 0.55, "tiktok": 0.2, "instagram": 0.15, "linkedin": 0.05, "twitter": 0.05}
    else:
        allocation = {"youtube": 0.45, "tiktok": 0.25, "instagram": 0.18, "linkedin": 0.06, "twitter": 0.06}

    return {
        "scale": round(scale, 2),
        "target_candidates_per_source": target_candidates,
        "target_publishable_clips_per_source": target_publishable,
        "experiment_rate": policy.experiment_rate,
        "platform_allocation": allocation,
        "actions": actions,
        "should_publish": perf.publish_success_rate >= 0.5,
    }
