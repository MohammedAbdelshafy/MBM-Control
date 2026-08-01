"""Stage 9.5: Virality — analyze uploaded video with Higgsfield brain_activity (Virality Predictor)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.pipelines.base import PipelineContext
from app.core.config import get_settings
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger("pipelines.virality")


async def run(ctx: PipelineContext) -> dict[str, Any]:
    video_path = ctx.meta.get("video_path")
    if not video_path:
        return {"analyzed": False, "skipped": True, "reason": "no video_path in context"}

    video_file = Path(video_path)
    if not video_file.exists():
        return {"analyzed": False, "skipped": True, "reason": f"video not found: {video_path}"}

    try:
        from app.services.higgsfield_service import HiggsfieldService

        result = HiggsfieldService.analyze_virality(video_file)
        if result.get("success"):
            logger.info("Virality analysis complete")
            return {
                "analyzed": True,
                "provider": "higgsfield_brain_activity",
                "report": result.get("report"),
                "raw": result.get("job_data"),
            }
        return {"analyzed": False, "error": result.get("error")}
    except Exception as exc:
        logger.warning(f"Virality analysis failed: {exc}")
        return {"analyzed": False, "error": str(exc)}
