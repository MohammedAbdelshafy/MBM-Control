"""
Video Quality Gate — ffprobe-based actual file inspection.

Validates rendered video files against production standards.
Does NOT trust application-written metadata — inspects the encoded file itself.

Produces: PASS | FAIL | BLOCKED
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class VideoProbeResult:
    """Raw ffprobe output parsed into structured fields."""
    container: str = ""
    video_codec: str = ""
    audio_codec: str = ""
    width: int = 0
    height: int = 0
    aspect_ratio: str = ""
    frame_rate: float = 0.0
    video_bitrate_kbps: int = 0
    audio_bitrate_kbps: int = 0
    audio_sample_rate: int = 0
    audio_channels: int = 0
    duration: float = 0.0
    video_duration: float = 0.0
    audio_duration: float = 0.0
    file_size_bytes: int = 0
    nb_frames: int = 0
    pixel_format: str = ""
    level: str = ""
    profile: str = ""
    error: str = ""


@dataclass
class GateResult:
    """Result from a single quality gate check."""
    gate: str = "VIDEO_GATE"
    status: str = "PASS"  # PASS | FAIL | BLOCKED
    reason: str = ""
    checks: Dict[str, bool] = field(default_factory=dict)
    probe: Optional[VideoProbeResult] = None
    severity: str = "info"  # info | warning | error | critical

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate": self.gate,
            "status": self.status,
            "reason": self.reason,
            "checks": self.checks,
            "severity": self.severity,
            "checks_passed": sum(1 for v in self.checks.values() if v),
            "checks_total": len(self.checks),
        }


def ffprobe_json(video_path: Path) -> VideoProbeResult:
    """Run ffprobe and return parsed VideoProbeResult."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_format", "-show_streams",
        "-print_format", "json",
        str(video_path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if res.returncode != 0:
            return VideoProbeResult(error=f"ffprobe failed: {res.stderr[:200]}")
        data = json.loads(res.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError) as e:
        return VideoProbeResult(error=str(e))

    result = VideoProbeResult()

    # Format info
    fmt = data.get("format", {})
    result.container = fmt.get("format_name", "")
    result.duration = float(fmt.get("duration", 0))
    result.file_size_bytes = int(fmt.get("size", 0))

    # Stream info
    streams = data.get("streams", [])
    for s in streams:
        codec_type = s.get("codec_type", "")
        if codec_type == "video" and not result.video_codec:
            result.video_codec = s.get("codec_name", "")
            result.width = int(s.get("width", 0))
            result.height = int(s.get("height", 0))
            result.aspect_ratio = s.get("display_aspect_ratio", "")
            result.pixel_format = s.get("pix_fmt", "")
            result.profile = s.get("profile", "")
            result.level = str(s.get("level", ""))
            result.nb_frames = int(s.get("nb_frames", 0))
            fps_str = s.get("r_frame_rate", "0/1")
            if "/" in fps_str:
                num, den = fps_str.split("/")
                try:
                    result.frame_rate = round(int(num) / int(den), 2) if int(den) else 0
                except (ValueError, ZeroDivisionError):
                    result.frame_rate = 0
            else:
                try:
                    result.frame_rate = float(fps_str)
                except ValueError:
                    result.frame_rate = 0
            try:
                result.video_bitrate_kbps = int(s.get("bit_rate", 0)) // 1000
            except (ValueError, TypeError):
                result.video_bitrate_kbps = 0
            try:
                result.video_duration = float(s.get("duration", 0))
            except (ValueError, TypeError):
                result.video_duration = 0
        elif codec_type == "audio" and not result.audio_codec:
            result.audio_codec = s.get("codec_name", "")
            result.audio_sample_rate = int(s.get("sample_rate", 0))
            result.audio_channels = int(s.get("channels", 0))
            try:
                result.audio_bitrate_kbps = int(s.get("bit_rate", 0)) // 1000
            except (ValueError, TypeError):
                result.audio_bitrate_kbps = 0
            try:
                result.audio_duration = float(s.get("duration", 0))
            except (ValueError, TypeError):
                result.audio_duration = 0

    return result


def validate_video_file(
    video_path: Path,
    *,
    expected_width: int = 1080,
    expected_height: int = 1920,
    min_bitrate_kbps: int = 500,
    max_bitrate_kbps: int = 30000,
    min_duration: float = 1.0,
    max_duration: float = 180.0,
    expected_fps_range: tuple = (24, 60),
    require_audio: bool = True,
    allowed_video_codecs: tuple = ("h264", "h265", "hevc", "vp9", "av1"),
    allowed_audio_codecs: tuple = ("aac", "mp3", "opus", "vorbis"),
) -> GateResult:
    """Validate a real video file using ffprobe. Returns PASS/FAIL/BLOCKED."""
    gate = GateResult()

    if not video_path.exists():
        gate.status = "BLOCKED"
        gate.reason = f"File not found: {video_path}"
        gate.severity = "critical"
        return gate

    probe = ffprobe_json(video_path)
    gate.probe = probe

    if probe.error:
        gate.status = "BLOCKED"
        gate.reason = f"ffprobe error: {probe.error}"
        gate.severity = "critical"
        return gate

    checks = {}

    # Container check
    checks["has_container"] = bool(probe.container)

    # Video codec
    checks["video_codec_valid"] = probe.video_codec.lower() in allowed_video_codecs

    # Audio codec
    if require_audio:
        checks["audio_codec_valid"] = probe.audio_codec.lower() in allowed_audio_codecs
        checks["has_audio_stream"] = bool(probe.audio_codec)
    else:
        checks["audio_codec_valid"] = True
        checks["has_audio_stream"] = True

    # Resolution
    checks["width_correct"] = probe.width == expected_width
    checks["height_correct"] = probe.height == expected_height
    checks["aspect_ratio_9_16"] = probe.aspect_ratio in ("9:16", "0.5625:1")

    # Frame rate
    checks["fps_in_range"] = expected_fps_range[0] <= probe.frame_rate <= expected_fps_range[1]

    # Bitrate
    checks["bitrate_not_too_low"] = probe.video_bitrate_kbps >= min_bitrate_kbps
    checks["bitrate_not_too_high"] = probe.video_bitrate_kbps <= max_bitrate_kbps

    # Duration
    checks["duration_valid"] = min_duration <= probe.duration <= max_duration

    # Audio-video sync
    if probe.video_duration > 0 and probe.audio_duration > 0:
        drift = abs(probe.video_duration - probe.audio_duration)
        checks["av_sync_within_1s"] = drift <= 1.0
    else:
        checks["av_sync_within_1s"] = True

    # Pixel format
    checks["pixel_format_valid"] = probe.pixel_format in ("yuv420p", "yuv420p10le", "yuv444p", "yuv422p")

    # Has frames
    checks["has_frames"] = probe.nb_frames > 0 if probe.nb_frames else probe.duration > 0

    gate.checks = checks
    passed = sum(1 for v in checks.values() if v)
    total = len(checks)
    failed_critical = [
        k for k, v in checks.items()
        if not v and k in ("video_codec_valid", "has_audio_stream", "duration_valid", "has_frames")
    ]

    if failed_critical:
        gate.status = "FAIL"
        gate.reason = f"Critical checks failed: {', '.join(failed_critical)} ({passed}/{total} passed)"
        gate.severity = "critical"
    elif passed < total * 0.7:
        gate.status = "FAIL"
        gate.reason = f"Too many checks failed ({passed}/{total} passed, need >= 70%)"
        gate.severity = "error"
    elif passed < total:
        gate.status = "PASS"
        gate.reason = f"Passed with warnings ({passed}/{total} checks passed)"
        gate.severity = "warning"
    else:
        gate.status = "PASS"
        gate.reason = f"All {total} checks passed"

    return gate
