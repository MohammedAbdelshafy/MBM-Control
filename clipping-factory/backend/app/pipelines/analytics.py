"""Stage 9: Analytics — collect/placeholder YouTube analytics for the upload."""
from __future__ import annotations

from typing import Any

from app.pipelines.base import PipelineContext
from app.core.logging_config import get_logger

logger = get_logger("pipelines.analytics")


async def run(ctx: PipelineContext) -> dict[str, Any]:
    # Real analytics require the YouTube Data API + OAuth. We surface what we
    # have and leave a hook for the analytics service to fill later.
    video_id = ctx.get("upload", "youtube_video_id")
    return {
        "video_id": video_id,
        "views": None,
        "watch_time_minutes": None,
        "ctr": None,
        "note": "analytics available after upload + 24h via YouTube Analytics API",
    }
