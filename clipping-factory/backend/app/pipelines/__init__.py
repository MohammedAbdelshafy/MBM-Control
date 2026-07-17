"""
Pipeline primitives for the jarvis-mbm YouTube media factory.

Stages are pure functions that take a PipelineContext, do one unit of work,
and return a StageResult. The orchestrator (youtube_pipeline.py) chains them
in the order defined by the mission:

  Trending Topics -> Research -> Script -> Voice -> Subtitles ->
  Thumbnail -> Metadata -> Upload -> Analytics -> Optimization
"""
from __future__ import annotations

import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable

from app.core.config import get_settings
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger("pipelines.base")

STAGE_ORDER = [
    "trends",
    "research",
    "script",
    "voice",
    "subtitles",
    "thumbnail",
    "metadata",
    "upload",
    "analytics",
    "optimize",
]


@dataclass
class StageResult:
    name: str
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: str | None = None
    duration_seconds: float = 0.0

    def to_dict(self) -> dict:
        return {
            "stage": self.name,
            "success": self.success,
            "duration_seconds": round(self.duration_seconds, 3),
            "error": self.error,
            "data": self.data,
        }


@dataclass
class PipelineContext:
    """Mutable state passed between stages. `topic` seeds the whole flow."""

    topic: str
    niche: str = "general"
    artifacts: dict[str, Any] = field(default_factory=dict)
    results: list[StageResult] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    # Directories (resolved from settings, created on demand)
    @property
    def dirs(self) -> dict:
        return settings.pipeline_dirs

    def add_result(self, result: StageResult) -> None:
        self.results.append(result)

    def get(self, stage: str, key: str, default: Any = None) -> Any:
        for r in self.results:
            if r.name == stage and key in r.data:
                return r.data[key]
        return self.artifacts.get(f"{stage}.{key}", default)

    def summary(self) -> dict:
        return {
            "topic": self.topic,
            "niche": self.niche,
            "stages": [r.to_dict() for r in self.results],
            "meta": self.meta,
        }


async def run_stage(
    name: str,
    fn: Callable[[PipelineContext], Awaitable[dict]],
    ctx: PipelineContext,
) -> StageResult:
    """Run a stage function, wrap output in StageResult, never raise."""
    start = time.time()
    try:
        data = await fn(ctx) or {}
        return StageResult(name=name, success=True, data=data, duration_seconds=time.time() - start)
    except Exception as exc:  # noqa: BLE001 — pipeline must be resilient
        logger.error(f"Stage '{name}' failed: {exc}\n{traceback.format_exc()}")
        return StageResult(
            name=name,
            success=False,
            error=str(exc),
            duration_seconds=time.time() - start,
        )
