"""Stage 5: Subtitles — produce an SRT caption file for the script."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.pipelines.base import PipelineContext
from app.core.config import get_settings
from app.core.logging_config import get_logger

settings = get_settings()
logger = get_logger("pipelines.subtitles")


def _to_srt(text: str, chars_per_sec: float = 14.0) -> str:
    words = text.split()
    if not words:
        return ""
    lines: list[str] = []
    idx = 1
    t = 0.0
    buf: list[str] = []
    for w in words:
        buf.append(w)
        line = " ".join(buf)
        if len(line) >= 32 or w is words[-1]:
            dur = max(1.0, len(line) / chars_per_sec)
            start = t
            end = t + dur
            h, m, s, ms = int(start // 3600), int((start % 3600) // 60), int(start % 60), int((start % 1) * 1000)
            he, me, se, mse = int(end // 3600), int((end % 3600) // 60), int(end % 60), int((end % 1) * 1000)
            lines.append(f"{idx}")
            lines.append(f"{h:02d}:{m:02d}:{s:02d},{ms:03d} --> {he:02d}:{me:02d}:{se:02d},{mse:03d}")
            lines.append(line)
            lines.append("")
            idx += 1
            t = end
            buf = []
    return "\n".join(lines)


async def run(ctx: PipelineContext) -> dict[str, Any]:
    script = ctx.get("script", "script") or {}
    text = (script.get("body") or ctx.topic)

    out_dir = settings.pipeline_dirs["transcripts"]
    out_path: Path = out_dir / f"captions_{abs(hash(ctx.topic))}.srt"
    srt = _to_srt(text)
    try:
        out_path.write_text(srt, encoding="utf-8")
    except Exception as exc:
        logger.warning(f"Subtitle write skipped: {exc}")

    return {"srt_path": str(out_path) if srt else None, "srt": srt}
