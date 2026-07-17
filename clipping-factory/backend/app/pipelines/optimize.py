"""Stage 10: Optimization — suggest improvements from the run for next iteration."""
from __future__ import annotations

from typing import Any

from app.pipelines.base import PipelineContext
from app.core.logging_config import get_logger

logger = get_logger("pipelines.optimize")


async def run(ctx: PipelineContext) -> dict[str, Any]:
    failed = [r.name for r in ctx.results if not r.success]
    suggestions: list[str] = []
    if "upload" in failed:
        suggestions.append("Enable YOUTUBE_OAUTH_ENABLED and run youtube_oauth_setup.py to publish.")
    if "voice" in failed:
        suggestions.append("edge-tts unavailable; install via pip and ensure network access.")
    if not failed:
        suggestions.append("Pipeline completed; consider A/B testing hooks via Langflow.")

    return {
        "failed_stages": failed,
        "suggestions": suggestions,
        "next_action": "schedule_follow_up" if failed else "monitor_analytics",
    }
