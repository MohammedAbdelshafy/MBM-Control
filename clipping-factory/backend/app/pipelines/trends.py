"""Stage 1: Trending Topics — find what's hot in the niche."""
from __future__ import annotations

from typing import Any

from app.pipelines.base import PipelineContext
from app.core.logging_config import get_logger

logger = get_logger("pipelines.trends")

_TRENDS_PROMPT = """You are a YouTube trend analyst. Given a niche, return the
top 5 trending video angles right now. Respond ONLY with valid JSON:

{{"trends": [{{"title": str, "angle": str, "why_trending": str}}]}}

Niche: {niche}
Topic hint: {topic}
"""


async def run(ctx: PipelineContext) -> dict[str, Any]:
    from app.services.ai_service import AIService

    ai = AIService()
    prompt = _TRENDS_PROMPT.format(niche=ctx.niche, topic=ctx.topic)
    raw = ai.complete(prompt, system="You are a concise data-driven trend analyst.")
    import json

    trends: list[dict] = []
    try:
        trends = json.loads(raw or "{}").get("trends", [])
    except Exception:
        # Fallback: one trend derived from the topic.
        trends = [{"title": ctx.topic, "angle": "overview", "why_trending": "seed topic"}]

    if not trends:
        trends = [{"title": ctx.topic, "angle": "overview", "why_trending": "seed topic"}]

    return {"trends": trends, "selected": trends[0]}
