"""
Compatibility shim for the former root-level `mbm_social_autonomous_runtime.py`.

The original file HARD-CODED 16 "PASSED" steps and FABRICATED analytics
(views=100000, revenue_usd=1850) into ChannelMetrics.json. It has been
quarantined to `mbm_social_autonomous_runtime.py.QUARANTINED`.

This shim preserves the old import surface but delegates to the REAL,
honest implementation in the `mbm_social` package. It never fabricates data.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent.parent


def _resolve_runtime():
    from mbm_social import autonomous_runtime as rt
    return rt


def _resolve_night():
    from mbm_social import night_operations as no
    return no


def _resolve_platforms():
    from mbm_social import platform_registry as pr
    return pr


class PlatformRegistry:
    """Delegates to the real capability matrix (honest status per platform)."""

    @classmethod
    def get_platform_config(cls, platform_id: str) -> dict:
        return _resolve_platforms().get_capability(platform_id)

    @classmethod
    def publish_status(cls, platform_id: str) -> str:
        return _resolve_platforms().publish_status(platform_id)


class LearningEngine:
    """Delegates to the real learning engine (no fabricated rows)."""

    def __init__(self, metrics_file: Optional[str] = None):
        from mbm_social import learning_engine as le
        self._le = le

    def record_clip_performance(self, *args, **kwargs):
        # Real learning engine writes accumulated, validated metrics — never
        # free-form invented ones. Callers should use learning_engine directly.
        raise NotImplementedError(
            "Use mbm_social.learning_engine to record real, measured performance."
        )


class NightOperationsDaemon:
    """Runs the REAL night missions (no canned SUCCESS)."""

    MISSIONS = [
        "Repository Audit", "Campaign Health Check", "Analytics Collection",
        "Model Health", "Learning Update", "Queue Optimization",
        "Platform Health", "Daily Executive Report", "Opportunity Scan",
        "Repository Backup",
    ]

    @staticmethod
    def execute_night_operations() -> dict:
        return _resolve_night().run_all_missions()


class MBMSocialAutonomousRuntime:
    """Delegates to the real 14-stage autonomous runtime."""

    def __init__(self, mode: str = "MBM_INTERNAL"):
        self.mode = mode

    def run_16_step_campaign_pipeline(
        self,
        campaign_name: str,
        profile: str = "dark_stories",
        target_brand: str = "clippingfactorymbm",
    ) -> dict:
        rt = _resolve_runtime()
        campaign_id = f"{profile}_{target_brand}_{campaign_name}".replace(" ", "_")
        return rt.run_autonomous_campaign(
            campaign_id=campaign_id,
            brand=target_brand,
            profile_name=profile,
            mode="internal",
        )


if __name__ == "__main__":
    runtime = MBMSocialAutonomousRuntime(mode="MBM_INTERNAL")
    res = runtime.run_16_step_campaign_pipeline(
        "Daily Campaign", profile="dark_stories", target_brand="clippingfactorymbm"
    )
    night_res = NightOperationsDaemon.execute_night_operations()
    print("Runtime stages:", len(res.get("stages", [])))
    print("Night missions:", len(night_res.get("missions", [])))
