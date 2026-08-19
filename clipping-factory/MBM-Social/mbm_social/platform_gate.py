"""
Platform Format Gate — validates that rendered output matches platform specs.

Tests: YouTube Shorts, Instagram Reels, TikTok, plus any additional platforms.

Produces: PASS | FAIL | BLOCKED per platform
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .video_gate import VideoProbeResult, ffprobe_json


@dataclass
class PlatformSpec:
    """Platform-specific video requirements."""
    name: str
    width: int
    height: int
    aspect_ratio: str
    max_duration_sec: int
    min_duration_sec: int
    allowed_codecs: tuple = ("h264", "h265", "hevc")
    allowed_audio_codecs: tuple = ("aac", "mp3")
    max_file_size_mb: int = 100
    recommended_fps: tuple = (30, 60)
    requires_vertical: bool = True


# Platform specifications
PLATFORM_SPECS: Dict[str, PlatformSpec] = {
    "youtube_shorts": PlatformSpec(
        name="YouTube Shorts",
        width=1080,
        height=1920,
        aspect_ratio="9:16",
        max_duration_sec=60,
        min_duration_sec=3,
        max_file_size_mb=256,
    ),
    "instagram_reels": PlatformSpec(
        name="Instagram Reels",
        width=1080,
        height=1920,
        aspect_ratio="9:16",
        max_duration_sec=90,
        min_duration_sec=3,
        max_file_size_mb=100,
    ),
    "tiktok": PlatformSpec(
        name="TikTok",
        width=1080,
        height=1920,
        aspect_ratio="9:16",
        max_duration_sec=600,
        min_duration_sec=3,
        max_file_size_mb=287,
    ),
}


@dataclass
class PlatformGateResult:
    gate: str = "PLATFORM_GATE"
    platform: str = ""
    status: str = "PASS"
    reason: str = ""
    checks: Dict[str, bool] = field(default_factory=dict)
    severity: str = "info"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "gate": self.gate,
            "platform": self.platform,
            "status": self.status,
            "reason": self.reason,
            "checks": self.checks,
            "severity": self.severity,
            "checks_passed": sum(1 for v in self.checks.values() if v),
            "checks_total": len(self.checks),
        }


def validate_platform(
    video_path: Path,
    platform: str,
) -> PlatformGateResult:
    """Validate a video file against a platform's specs."""
    gate = PlatformGateResult(platform=platform)

    if platform not in PLATFORM_SPECS:
        gate.status = "BLOCKED"
        gate.reason = f"Unknown platform: {platform}"
        gate.severity = "error"
        return gate

    spec = PLATFORM_SPECS[platform]

    if not video_path.exists():
        gate.status = "BLOCKED"
        gate.reason = f"File not found: {video_path}"
        gate.severity = "critical"
        return gate

    probe = ffprobe_json(video_path)
    if probe.error:
        gate.status = "BLOCKED"
        gate.reason = f"Cannot probe file: {probe.error}"
        gate.severity = "critical"
        return gate

    checks = {}

    # Resolution
    checks["width"] = probe.width == spec.width
    checks["height"] = probe.height == spec.height
    checks["aspect_ratio"] = probe.aspect_ratio == spec.aspect_ratio

    # Duration
    checks["duration_min"] = probe.duration >= spec.min_duration_sec
    checks["duration_max"] = probe.duration <= spec.max_duration_sec

    # Codec
    checks["video_codec"] = probe.video_codec.lower() in spec.allowed_codecs
    checks["audio_codec"] = probe.audio_codec.lower() in spec.allowed_audio_codecs

    # File size
    file_size_mb = probe.file_size_bytes / (1024 * 1024)
    checks["file_size"] = file_size_mb <= spec.max_file_size_mb

    # FPS
    checks["fps"] = spec.recommended_fps[0] <= probe.frame_rate <= spec.recommended_fps[1]

    # Has audio
    checks["has_audio"] = bool(probe.audio_codec)

    gate.checks = checks

    passed = sum(1 for v in checks.values() if v)
    total = len(checks)
    failed_critical = [
        k for k, v in checks.items()
        if not v and k in ("width", "height", "duration_max", "video_codec", "has_audio")
    ]

    if failed_critical:
        gate.status = "FAIL"
        gate.reason = f"Platform {spec.name} critical failures: {', '.join(failed_critical)} ({passed}/{total} passed)"
        gate.severity = "critical"
    elif passed < total:
        gate.status = "PASS"
        gate.reason = f"Platform {spec.name} passed with warnings ({passed}/{total} checks)"
        gate.severity = "warning"
    else:
        gate.status = "PASS"
        gate.reason = f"Platform {spec.name} all checks passed ({passed}/{total})"

    return gate


def validate_all_platforms(video_path: Path) -> Dict[str, PlatformGateResult]:
    """Validate video against all known platform specs."""
    results = {}
    for platform in PLATFORM_SPECS:
        results[platform] = validate_platform(video_path, platform)
    return results
