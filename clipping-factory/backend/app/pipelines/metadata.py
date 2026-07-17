"""Stage 7: Metadata — title, description, hashtags, SEO tags."""
from __future__ import annotations

from typing import Any

from app.pipelines.base import PipelineContext
from app.core.logging_config import get_logger

logger = get_logger("pipelines.metadata")

_META_PROMPT = """Generate YouTube metadata for a short. Respond ONLY with JSON:

{{"title": str, "description": str, "tags": [str], "hashtags": [str]}}

Angle: {angle}
Hook: {hook}
Facts: {facts}
"""


async def run(ctx: PipelineContext) -> dict[str, Any]:
    from app.services.ai_service import AIService

    angle = ctx.get("research", "angle") or ctx.topic
    hook = (ctx.get("script", "script") or {}).get("hook", "")
    facts = ctx.get("research", "facts") or []

    ai = AIService()
    raw = ai.complete(
        _META_PROMPT.format(angle=angle, hook=hook, facts="\n".join(f"- {f}" for f in facts)),
        system="You are a YouTube SEO specialist.",
    )
    import json

    meta = {
        "title": angle,
        "description": f"{hook}\n\n{angle}",
        "tags": [ctx.niche, "shorts"],
        "hashtags": ["#shorts", f"#{ctx.niche.replace(' ', '')}"],
    }
    try:
        meta.update(json.loads(raw or "{}"))
    except Exception:
        pass

    return {"metadata": meta}
