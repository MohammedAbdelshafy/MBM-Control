"""Stage 6: Thumbnail — generate a thumbnail prompt (and image if ComfyUI set)."""
from __future__ import annotations

from typing import Any

from app.pipelines.base import PipelineContext
from app.core.logging_config import get_logger

logger = get_logger("pipelines.thumbnail")

_THUMB_PROMPT = """Design a high-CTR YouTube thumbnail for this video.
Return ONLY valid JSON:

{{"prompt": str, "text_overlay": str, "style": str, "colors": [str]}}

Angle: {angle}
Hook: {hook}
"""


async def run(ctx: PipelineContext) -> dict[str, Any]:
    from app.services.ai_service import AIService

    angle = ctx.get("research", "angle") or ctx.topic
    hook = (ctx.get("script", "script") or {}).get("hook", "")

    ai = AIService()
    raw = ai.complete(
        _THUMB_PROMPT.format(angle=angle, hook=hook),
        system="You are a YouTube thumbnail designer focused on click-through rate.",
    )
    import json

    thumb = {"prompt": f"{angle} — bold thumbnail", "text_overlay": hook, "style": "high-contrast", "colors": ["#FF0000", "#FFFFFF"]}
    try:
        thumb.update(json.loads(raw or "{}"))
    except Exception:
        pass

    return {"thumbnail_prompt": thumb, "image_path": None, "note": "image generation optional (ComfyUI)"}
