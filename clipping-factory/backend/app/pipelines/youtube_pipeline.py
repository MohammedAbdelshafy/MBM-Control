"""
YouTube pipeline orchestrator.

Chains the ten stages in the order required by the mission:

  Trending Topics -> Research -> Script -> Voice -> Subtitles ->
  Thumbnail -> Metadata -> Upload -> Analytics -> Optimization

Each stage is wrapped by run_stage so a failure in one step never aborts the
whole run — the final summary reports every stage's outcome.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.pipelines.base import PipelineContext, run_stage, STAGE_ORDER
from app.pipelines import trends, research, script, voice, subtitles, thumbnail, metadata, upload, analytics, optimize
from app.core.config import get_settings
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger("pipelines.youtube")

_STAGE_FNS = {
    "trends": trends.run,
    "research": research.run,
    "script": script.run,
    "voice": voice.run,
    "subtitles": subtitles.run,
    "thumbnail": thumbnail.run,
    "metadata": metadata.run,
    "upload": upload.run,
    "analytics": analytics.run,
    "optimize": optimize.run,
}


async def run_pipeline(
    topic: str,
    niche: str = "general",
    video_path: str | None = None,
    stages: list[str] | None = None,
) -> dict[str, Any]:
    """Run the full (or subset) YouTube pipeline. Returns a JSON-serialisable summary."""
    ctx = PipelineContext(topic=topic, niche=niche)
    if video_path:
        ctx.meta["video_path"] = video_path

    order = stages or STAGE_ORDER
    for name in order:
        fn = _STAGE_FNS.get(name)
        if not fn:
            logger.warning(f"No implementation for stage '{name}' — skipping")
            continue
        result = await run_stage(name, fn, ctx)
        ctx.add_result(result)

    summary = ctx.summary()
    summary["finished_at"] = datetime.now(timezone.utc).isoformat()
    summary["all_passed"] = all(r.success for r in ctx.results)

    # Persist a run report for auditability.
    try:
        reports = settings.pipeline_dirs["pipeline"] / "runs"
        reports.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
        safe = "".join(c for c in topic[:40] if c.isalnum() or c in "-_ ")
        (reports / f"{stamp}_{safe or 'run'}.json").write_text(
            json.dumps(summary, indent=2, default=str), encoding="utf-8"
        )
    except Exception as exc:
        logger.warning(f"Could not persist pipeline report: {exc}")

    return summary
