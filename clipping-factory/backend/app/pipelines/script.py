"""Stage 3: Script — write the video script + hook."""
from __future__ import annotations

from typing import Any

from app.pipelines.base import PipelineContext
from app.core.logging_config import get_logger

logger = get_logger("pipelines.script")

_SCRIPT_PROMPT = """Write a YouTube {format} script for the angle below.
Include a 1-sentence hook, the body (spoken narration), and a CTA.
Respond ONLY with valid JSON:

{{"hook": str, "body": str, "cta": str, "est_seconds": int}}

Angle: {angle}
Facts: {facts}
Target length: {length} seconds
"""


async def run(ctx: PipelineContext, format: str = "short", length: int = 45) -> dict[str, Any]:
    from app.services.ai_service import AIService

    angle = ctx.get("research", "angle") or ctx.topic
    facts = ctx.get("research", "facts") or []

    ai = AIService()
    prompt = _SCRIPT_PROMPT.format(
        format=format, angle=angle, facts="\n".join(f"- {f}" for f in facts), length=length
    )
    raw = ai.complete(prompt, system="You are a viral YouTube scriptwriter.")
    import json

    script = {"hook": "", "body": angle, "cta": "Follow for more!", "est_seconds": length}
    try:
        script.update(json.loads(raw or "{}"))
    except Exception:
        pass

    return {"script": script, "format": format}
