"""Stage 2: Research — gather supporting facts for the selected angle."""
from __future__ import annotations

from typing import Any

from app.pipelines.base import PipelineContext
from app.core.logging_config import get_logger

logger = get_logger("pipelines.research")

_RESEARCH_PROMPT = """Research the following YouTube video angle and produce
3-5 concise factual bullet points a creator can use on-screen. Respond ONLY
with valid JSON:

{{"facts": [str], "sources": [str]}}

Angle: {angle}
Niche: {niche}
"""


async def run(ctx: PipelineContext) -> dict[str, Any]:
    from app.services.ai_service import AIService

    selected = ctx.get("trends", "selected") or {"angle": ctx.topic}
    angle = selected.get("angle") or selected.get("title") or ctx.topic

    ai = AIService()
    prompt = _RESEARCH_PROMPT.format(angle=angle, niche=ctx.niche)
    raw = ai.complete(prompt, system="You are a meticulous researcher. Cite only verifiable facts.")
    import json

    facts: list[str] = []
    sources: list[str] = []
    try:
        parsed = json.loads(raw or "{}")
        facts = parsed.get("facts", [])
        sources = parsed.get("sources", [])
    except Exception:
        facts = [angle]

    return {"facts": facts, "sources": sources, "angle": angle}
