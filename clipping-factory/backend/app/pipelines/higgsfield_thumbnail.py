"""Stage 6v: Thumbnail — generate prompt via LLM, actual image via Higgsfield GPT Image 2."""
from __future__ import annotations

from typing import Any

from app.pipelines.base import PipelineContext
from app.core.config import get_settings
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger("pipelines.higgsfield_thumbnail")


async def run(ctx: PipelineContext) -> dict[str, Any]:
    from app.services.ai_service import AIService

    angle = ctx.get("research", "angle") or ctx.topic
    hook = (ctx.get("script", "script") or {}).get("hook", "")

    ai = AIService()
    raw = ai.complete(
        _THUMB_PROMPT.format(angle=angle, hook=hook),
        system="You are a YouTube thumbnail designer focused on click-through rate.",
    )

    thumb = {
        "prompt": f"{angle} — bold thumbnail",
        "text_overlay": hook,
        "style": "high-contrast",
        "colors": ["#FF0000", "#FFFFFF"],
    }
    try:
        import json
        thumb.update(json.loads(raw or "{}"))
    except Exception:
        pass

    image_path = None
    try:
        from app.services.higgsfield_service import HiggsfieldService

        out_dir = settings.pipeline_dirs["thumbnails"]
        out_file = out_dir / f"thumb_{abs(hash(ctx.topic))}.png"
        ok = HiggsfieldService.generate_thumbnail(
            prompt=thumb["prompt"],
            text_overlay=thumb["text_overlay"],
            output_path=out_file,
        )
        if ok and out_file.exists():
            image_path = str(out_file)
            logger.info("Higgsfield thumbnail image generated")
    except Exception as exc:
        logger.warning(f"Higgsfield thumbnail generation failed: {exc}")

    return {
        "thumbnail_prompt": thumb,
        "image_path": image_path,
        "note": "generated via Higgsfield GPT Image 2" if image_path else "LLM prompt only (Higgsfield unavailable)",
    }


_THUMB_PROMPT = """Design a high-CTR YouTube thumbnail for this video.
Return ONLY valid JSON:

{{"prompt": str, "text_overlay": str, "style": str, "colors": [str]}}

Angle: {angle}
Hook: {hook}
"""
