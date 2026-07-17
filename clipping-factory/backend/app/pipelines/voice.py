"""Stage 4: Voice — generate a TTS voiceover from the script body."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from app.pipelines.base import PipelineContext
from app.core.config import get_settings
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger("pipelines.voice")


async def run(ctx: PipelineContext) -> dict[str, Any]:
    script = ctx.get("script", "script") or {}
    body = (script.get("body") or ctx.topic)[:4000]

    out_dir = settings.pipeline_dirs["uploads"]
    out_path: Path = out_dir / f"voiceover_{abs(hash(ctx.topic))}.mp3"

    try:
        from app.services.video_processor import VideoProcessor

        ok = VideoProcessor.generate_voiceover_sync(
            body,
            out_path,
            settings.voiceover_default_voice,
            settings.voiceover_default_rate,
            settings.voiceover_default_pitch,
        )
        if ok and out_path.exists():
            return {"voiceover_path": str(out_path), "voice": settings.voiceover_default_voice}
    except Exception as exc:
        logger.warning(f"Voice generation skipped: {exc}")

    return {"voiceover_path": None, "voice": None, "skipped": True}
