"""Stage 5.5: Scene Gen — generate scene images from the script via Higgsfield GPT Image 2."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.pipelines.base import PipelineContext
from app.core.config import get_settings
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger("pipelines.scene_gen")


async def run(ctx: PipelineContext) -> dict[str, Any]:
    script = ctx.get("script", "script") or {}
    body = script.get("body", ctx.topic)
    hook = script.get("hook", "")

    from app.services.ai_service import AIService
    ai = AIService()
    raw = ai.complete(
        _SCENE_PROMPT.format(body=body[:2000], hook=hook[:200]),
        system="You are a visual director. Output only JSON.",
    )

    scenes = []
    try:
        scenes = json.loads(raw or "[]")
        if isinstance(scenes, dict):
            scenes = scenes.get("scenes", [scenes])
    except Exception:
        scenes = [{"prompt": hook or body[:100], "keywords": [ctx.topic]}]

    scene_count = min(len(scenes), 4)
    scene_paths = []
    from app.services.higgsfield_service import HiggsfieldService

    out_dir = settings.pipeline_dirs["uploads"]
    for i in range(scene_count):
        prompt = scenes[i].get("prompt", scenes[i].get("description", str(scenes[i])))
        scene_file = out_dir / f"scene_{abs(hash(ctx.topic))}_{i}.png"
        try:
            ok = HiggsfieldService.generate_image(prompt, scene_file, aspect_ratio="16:9")
            if ok and scene_file.exists():
                scene_paths.append(str(scene_file))
                logger.info(f"Scene {i} image generated")
        except Exception as exc:
            logger.warning(f"Scene {i} generation failed: {exc}")

    return {
        "scene_count": len(scene_paths),
        "scene_paths": scene_paths,
        "scenes": scenes[:scene_count] if scene_paths else [],
        "all_prompts": [s.get("prompt", s.get("description", "")) for s in scenes[:scene_count]],
    }


_SCENE_PROMPT = """You are a visual director creating YouTube video scene descriptions.
Given a script body and hook, generate 2-4 distinct visual scenes for image generation.

Return ONLY a JSON array of objects:
[{{"prompt": "detailed image generation prompt for GPT Image 2", "keywords": [str], "duration_seconds": int}}]

Script: {body}
Hook: {hook}
"""
