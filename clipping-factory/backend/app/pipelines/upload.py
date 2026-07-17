"""Stage 8: Upload — publish to YouTube via OAuth (skips if not configured)."""
from __future__ import annotations

from typing import Any

from app.pipelines.base import PipelineContext
from app.core.config import get_settings
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger("pipelines.upload")


async def run(ctx: PipelineContext) -> dict[str, Any]:
    if not settings.youtube_oauth_enabled:
        return {
            "uploaded": False,
            "skipped": True,
            "reason": "YOUTUBE_OAUTH_ENABLED=false — run scripts/youtube_oauth_setup.py",
        }

    meta = ctx.get("metadata", "metadata") or {}
    # The pipeline produces metadata + a voiceover/thumbnail, but a finished
    # rendered MP4 is required to upload. If none exists, report what's ready.
    video_path = ctx.meta.get("video_path")
    if not video_path:
        return {
            "uploaded": False,
            "skipped": True,
            "reason": "no rendered video_path in context; supply a finished MP4",
            "ready_metadata": meta,
        }

    try:
        from app.services.youtube_upload import YouTubeUploader

        uploader = YouTubeUploader(tokens_path=str(settings.youtube_tokens_file()))
        video_id = uploader.upload_short(
            video_path=video_path,
            title=meta.get("title", ctx.topic),
            description=meta.get("description", ""),
            tags=meta.get("tags", []),
            privacy=settings.youtube_default_privacy,
        )
        return {"uploaded": bool(video_id), "youtube_video_id": video_id}
    except Exception as exc:
        logger.warning(f"YouTube upload skipped: {exc}")
        return {"uploaded": False, "error": str(exc)}
