"""
Production Pipeline — the actual render engine for Clipping Factory.

Invariant: NO_REAL_SOURCE → NO_CLIP
A clip is NEVER marked RENDERED without evidence of actual pipeline execution.

Output manifest tracks:
  source_id, source_uri, source_checksum, campaign_id, script_id,
  voice_id, render_started_at, render_completed_at, editor_version,
  qa_version, output_checksum
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class RenderStatus(str, Enum):
    PENDING = "pending"
    ACQUIRING = "acquiring"
    SCRIPTING = "scripting"
    VOICEOVER = "voiceover"
    RENDERING = "rendering"
    CAPTIONING = "captioning"
    QA = "qa"
    PACKAGING = "packaging"
    QUEUED = "queued"
    RENDERED = "rendered"
    FAILED = "failed"
    SOURCE_NOT_FOUND = "source_not_found"


@dataclass
class RenderManifest:
    """Immutable record of how a clip was produced. Evidence of real work."""
    manifest_id: str = ""
    source_id: str = ""
    source_uri: str = ""
    source_checksum: str = ""
    campaign_id: str = ""
    script_id: str = ""
    voice_id: str = ""
    render_started_at: str = ""
    render_completed_at: str = ""
    editor_version: str = "clipping_factory_v1"
    qa_version: str = "creative_gate_v1"
    output_checksum: str = ""
    output_path: str = ""
    output_duration_sec: float = 0.0
    output_width: int = 0
    output_height: int = 0
    output_fps: float = 0.0
    output_file_size_bytes: int = 0
    render_status: str = RenderStatus.PENDING
    pipeline_steps_completed: List[str] = field(default_factory=list)
    qa_scores: Dict[str, float] = field(default_factory=dict)
    creative_score: float = 0.0
    publish_provenance: str = ""
    error_message: str = ""

    def __post_init__(self):
        if not self.manifest_id:
            self.manifest_id = "RM-" + uuid.uuid4().hex[:12].upper()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _file_checksum(path: Path) -> str:
    """SHA-256 checksum of a file."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _probe_video(path: Path) -> Dict[str, Any]:
    """Extract video metadata via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_format", "-show_streams",
        "-print_format", "json",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        if result.returncode == 0:
            data = json.loads(result.stdout)
            fmt = data.get("format", {})
            streams = data.get("streams", [])
            vstream = next((s for s in streams if s.get("codec_type") == "video"), {})
            astream = next((s for s in streams if s.get("codec_type") == "audio"), {})

            fps_str = vstream.get("r_frame_rate", "0/1")
            try:
                num, den = fps_str.split("/")
                fps = int(num) / int(den) if int(den) else 0
            except Exception:
                fps = 0

            return {
                "duration": float(fmt.get("duration", 0)),
                "width": int(vstream.get("width", 0)),
                "height": int(vstream.get("height", 0)),
                "fps": fps,
                "size": int(fmt.get("size", 0)),
                "video_codec": vstream.get("codec_name", ""),
                "audio_codec": astream.get("codec_name", ""),
            }
    except Exception:
        pass
    return {"duration": 0, "width": 0, "height": 0, "fps": 0, "size": 0}


def _ffmpeg_render(
    source_path: Path,
    output_path: Path,
    target_width: int = 1080,
    target_height: int = 1920,
    target_fps: int = 30,
    duration_min: float = 0,
    duration_max: float = 999,
) -> bool:
    """
    Actually render a clip from source using FFmpeg.
    Returns True only if the output file exists and has valid video.
    """
    ffmpeg = os.getenv("FFMPEG_PATH", "ffmpeg")

    cmd = [
        ffmpeg, "-y",
        "-i", str(source_path),
        "-t", str(duration_max),
        "-vf", f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2",
        "-r", str(target_fps),
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "18",
        "-c:a", "aac",
        "-b:a", "128k",
        "-ar", "44100",
        "-movflags", "+faststart",
        "-loglevel", "error",
        str(output_path),
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if proc.returncode != 0:
            return False
    except Exception:
        return False

    return output_path.exists() and output_path.stat().st_size > 10000


def _generate_tts(
    text: str,
    output_path: Path,
    voice_id: str = "en-US-GuyNeural",
    rate: str = "-5%",
    pitch: str = "-2Hz",
) -> bool:
    """Generate TTS audio using edge-tts."""
    try:
        import edge_tts
        import asyncio

        async def _gen():
            communicate = edge_tts.Communicate(text, voice_id, rate=rate, pitch=pitch)
            await communicate.save(str(output_path))

        asyncio.run(_gen())
        return output_path.exists() and output_path.stat().st_size > 1000
    except ImportError:
        return False
    except Exception:
        return False


def _generate_captions_srt(
    caption_beats: List[Dict[str, Any]],
    output_path: Path,
) -> bool:
    """Generate SRT subtitle file from caption beats."""
    try:
        lines = []
        for i, beat in enumerate(caption_beats, 1):
            start = beat.get("timestamp_start", 0)
            end = beat.get("timestamp_end", start + 2)
            text = beat.get("text", "")

            def _fmt_ts(ts):
                h = int(ts // 3600)
                m = int((ts % 3600) // 60)
                s = int(ts % 60)
                ms = int((ts % 1) * 1000)
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

            lines.append(f"{i}")
            lines.append(f"{_fmt_ts(start)} --> {_fmt_ts(end)}")
            lines.append(text)
            lines.append("")

        output_path.write_text("\n".join(lines), encoding="utf-8")
        return output_path.exists()
    except Exception:
        return False


def render_clip(
    campaign_id: str,
    source_path: Optional[Path],
    script_data: Dict[str, Any],
    channel_profile: Dict[str, Any],
    output_dir: Path,
    voiceover_text: str = "",
) -> RenderManifest:
    """
    Render a single clip through the full pipeline.

    CRITICAL INVARIANT:
      If source_path is None or doesn't exist → SOURCE_NOT_FOUND
      We NEVER fall back to a demo file.
    """
    manifest = RenderManifest(
        campaign_id=campaign_id,
        script_id=script_data.get("script_id", ""),
        render_started_at=datetime.now(timezone.utc).isoformat(),
    )

    output_dir.mkdir(parents=True, exist_ok=True)

    # ── STEP 1: SOURCE VERIFICATION ──
    if source_path is None or not source_path.exists():
        manifest.render_status = RenderStatus.SOURCE_NOT_FOUND
        manifest.error_message = f"NO_REAL_SOURCE: {source_path}"
        manifest.render_completed_at = datetime.now(timezone.utc).isoformat()
        return manifest

    manifest.source_id = f"SRC-{campaign_id}"
    manifest.source_uri = str(source_path)
    manifest.source_checksum = _file_checksum(source_path)
    manifest.pipeline_steps_completed.append("source_verified")

    # ── STEP 2: VOICEOVER ──
    voice_config = channel_profile.get("voice_config", {})
    voiceover_path = output_dir / f"{campaign_id}_voiceover.mp3"

    if voiceover_text and voice_config.get("provider") == "edge_tts":
        voice_ok = _generate_tts(
            voiceover_text,
            voiceover_path,
            voice_id=voice_config.get("voice_id", "en-US-GuyNeural"),
            rate=voice_config.get("rate", "-5%"),
            pitch=voice_config.get("pitch", "-2Hz"),
        )
        if voice_ok:
            manifest.voice_id = voice_config.get("voice_id", "unknown")
            manifest.pipeline_steps_completed.append("voiceover_generated")
        else:
            manifest.render_status = RenderStatus.FAILED
            manifest.error_message = "TTS generation failed"
            manifest.render_completed_at = datetime.now(timezone.utc).isoformat()
            return manifest
    elif voiceover_text:
        # Fallback: write narration text for external TTS
        narration_path = output_dir / f"{campaign_id}_narration.txt"
        narration_path.write_text(voiceover_text, encoding="utf-8")
        manifest.pipeline_steps_completed.append("narration_written")

    # ── STEP 3: RENDER VIDEO ──
    output_video = output_dir / f"{campaign_id}_rendered.mp4"

    resolution = channel_profile.get("resolution", "1080x1920").split("x")
    target_w = int(resolution[0]) if len(resolution) == 2 else 1080
    target_h = int(resolution[1]) if len(resolution) == 2 else 1920
    target_fps = channel_profile.get("fps", 30)
    max_dur = channel_profile.get("target_duration_max", 75)

    render_ok = _ffmpeg_render(
        source_path, output_video,
        target_width=target_w, target_height=target_h,
        target_fps=target_fps, duration_max=float(max_dur),
    )

    if not render_ok:
        manifest.render_status = RenderStatus.FAILED
        manifest.error_message = "FFmpeg render failed — output file missing or too small"
        manifest.render_completed_at = datetime.now(timezone.utc).isoformat()
        return manifest

    manifest.pipeline_steps_completed.append("video_rendered")

    # ── STEP 4: GENERATE CAPTIONS ──
    caption_beats = script_data.get("caption_beats", [])
    if caption_beats:
        srt_path = output_dir / f"{campaign_id}_captions.srt"
        if _generate_captions_srt(caption_beats, srt_path):
            manifest.pipeline_steps_completed.append("captions_generated")

    # ── STEP 5: PROBE OUTPUT ──
    probe = _probe_video(output_video)
    manifest.output_path = str(output_video)
    manifest.output_duration_sec = probe.get("duration", 0)
    manifest.output_width = probe.get("width", 0)
    manifest.output_height = probe.get("height", 0)
    manifest.output_fps = probe.get("fps", 0)
    manifest.output_file_size_bytes = probe.get("size", 0)
    manifest.output_checksum = _file_checksum(output_video)

    # ── STEP 6: QA CHECK ──
    creative_score = 0.0
    qa_notes = []

    if probe.get("duration", 0) > 0:
        creative_score += 2.0
        qa_notes.append(f"Duration OK: {probe['duration']:.1f}s")
    else:
        qa_notes.append("Duration: 0s — FAIL")

    if probe.get("width", 0) >= 1080 and probe.get("height", 0) >= 1920:
        creative_score += 2.0
        qa_notes.append("Resolution OK: 1080x1920")

    if probe.get("fps", 0) >= 24:
        creative_score += 1.0
        qa_notes.append(f"FPS OK: {probe['fps']}")

    if probe.get("audio_codec"):
        creative_score += 1.5
        qa_notes.append(f"Audio: {probe['audio_codec']}")

    if probe.get("video_codec"):
        creative_score += 1.0
        qa_notes.append(f"Video: {probe['video_codec']}")

    if probe.get("size", 0) > 50000:
        creative_score += 0.5
        qa_notes.append("File size: adequate")

    manifest.qa_scores = {"technical_score": creative_score}
    manifest.creative_score = creative_score
    manifest.pipeline_steps_completed.append("qa_checked")

    # ── STEP 7: FINAL STATUS ──
    manifest.render_completed_at = datetime.now(timezone.utc).isoformat()

    if creative_score >= 6.0:
        manifest.render_status = RenderStatus.RENDERED
    else:
        manifest.render_status = RenderStatus.FAILED
        manifest.error_message = f"QA failed: {'; '.join(qa_notes)}"

    return manifest


def package_for_publish(
    manifest: RenderManifest,
    publish_queue_dir: Path,
    metadata: Dict[str, Any],
) -> Path:
    """
    Package a rendered clip for the publish queue.
    Copies the rendered video and writes a metadata JSON alongside it.
    Returns the path to the metadata file.
    """
    if manifest.render_status != RenderStatus.RENDERED:
        raise ValueError(
            f"Cannot package clip with status {manifest.render_status}. "
            "Only RENDERED clips can be packaged."
        )

    publish_queue_dir.mkdir(parents=True, exist_ok=True)

    source_video = Path(manifest.output_path)
    if not manifest.output_path or not source_video.exists() or source_video.is_dir():
        raise FileNotFoundError(f"Rendered video not found: {source_video}")

    dest_video = publish_queue_dir / f"{manifest.campaign_id}_final.mp4"
    shutil.copy2(str(source_video), str(dest_video))

    pkg = {
        "campaign_id": manifest.campaign_id,
        "script_id": manifest.script_id,
        "source_checksum": manifest.source_checksum,
        "output_checksum": _file_checksum(dest_video),
        "render_manifest": manifest.to_dict(),
        "metadata": metadata,
        "status": "QUEUED_FOR_PUBLISHING",
        "packaged_at": datetime.now(timezone.utc).isoformat(),
    }

    json_path = dest_video.with_suffix(".json")
    json_path.write_text(json.dumps(pkg, indent=2), encoding="utf-8")

    return json_path
