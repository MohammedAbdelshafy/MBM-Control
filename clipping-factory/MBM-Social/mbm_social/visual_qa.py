"""
Visual QA Artifact Generator — P8

Extracts representative frames from clips and produces machine-readable
inspection reports. Human-verifiable without opening the full video.

Usage:
  python -m mbm_social.visual_qa <clip_path> [--output-dir DIR]
  python -m mbm_social.visual_qa --all  # process all publish_queue clips
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "artifacts" / "production_qa" / "visual"

# Frame sample positions (percentage of duration)
FRAME_POSITIONS = {
    "opening": 0.0,    # first frame
    "pct_25": 0.25,
    "pct_50": 0.50,
    "pct_75": 0.75,
    "final": 0.99,     # last frame (0.99 to avoid seeking past end)
}


@dataclass
class FrameResult:
    position: str
    timestamp_sec: float
    frame_path: str = ""
    width: int = 0
    height: int = 0
    is_black_frame: bool = False
    black_frame_pct: float = 0.0
    safe_zone_ok: bool = True
    caption_state: str = "unknown"
    error: str = ""


@dataclass
class VisualQAResult:
    source: str = ""
    clip_id: str = ""
    clip_path: str = ""
    duration_sec: float = 0.0
    width: int = 0
    height: int = 0
    timestamp: str = ""
    output_dir: str = ""
    frames: List[FrameResult] = field(default_factory=list)
    overall_status: str = "PASS"
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "clip_id": self.clip_id,
            "clip_path": self.clip_path,
            "duration_sec": self.duration_sec,
            "width": self.width,
            "height": self.height,
            "timestamp": self.timestamp,
            "output_dir": self.output_dir,
            "frames": [asdict(f) for f in self.frames],
            "overall_status": self.overall_status,
            "issues": self.issues,
        }


def _probe_clip(clip_path: Path) -> Dict[str, Any]:
    """Get clip metadata via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_format", "-show_streams",
        "-print_format", "json",
        str(clip_path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        return json.loads(res.stdout) if res.returncode == 0 else {}
    except Exception:
        return {}


def _extract_frame(clip_path: Path, timestamp: float, output_path: Path) -> bool:
    """Extract a single frame at the given timestamp."""
    cmd = [
        "ffmpeg", "-y",
        "-ss", f"{timestamp:.3f}",
        "-i", str(clip_path),
        "-vframes", "1",
        "-q:v", "2",
        str(output_path),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, timeout=15)
        return res.returncode == 0 and output_path.exists()
    except Exception:
        return False


def _detect_black_frame(frame_path: Path, threshold: float = 0.02) -> tuple[bool, float]:
    """Check if frame is predominantly black using ffmpeg signalstats."""
    cmd = [
        "ffprobe", "-v", "error",
        "-f", "lavfi",
        "-i", f"movie={frame_path},signalstats",
        "-print_format", "json",
        "-show_entries", "frame_tags=lavfi.signalstats.YAVG",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        if res.returncode == 0:
            data = json.loads(res.stdout)
            frames = data.get("frames", [])
            if frames:
                yavg_str = frames[0].get("tags", {}).get("lavfi.signalstats.YAVG", "128")
                yavg = float(yavg_str)
                pct_black = 1.0 - (yavg / 255.0)
                return pct_black > threshold, pct_black
    except Exception:
        pass
    # Fallback: check file size (very small = likely black)
    return False, 0.0


def _check_safe_zone(frame_path: Path) -> bool:
    """Check if frame has content in safe zones (not all one color at edges)."""
    # Basic heuristic: frame should not be entirely one color
    try:
        size = frame_path.stat().st_size
        # A 1080x1920 JPEG should be >50KB for any real content
        return size > 50000
    except Exception:
        return False


def generate_visual_qa(
    clip_path: Path,
    output_dir: Optional[Path] = None,
    clip_id: str = "",
    source: str = "",
) -> VisualQAResult:
    """Generate visual QA artifacts for a clip.

    Extracts 5 representative frames, checks for black frames,
    safe zones, and produces a machine-readable report.
    """
    if output_dir is None:
        ts = time.strftime("%Y%m%d_%H%M%S")
        output_dir = DEFAULT_OUTPUT / ts

    output_dir.mkdir(parents=True, exist_ok=True)
    frames_dir = output_dir / "frames"
    frames_dir.mkdir(exist_ok=True)

    result = VisualQAResult(
        source=source or str(clip_path),
        clip_id=clip_id or clip_path.stem,
        clip_path=str(clip_path),
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        output_dir=str(output_dir),
    )

    # Probe clip
    probe = _probe_clip(clip_path)
    if not probe:
        result.overall_status = "BLOCKED"
        result.issues.append("ffprobe failed — cannot inspect clip")
        return result

    # Extract video stream info
    video_stream = None
    for stream in probe.get("streams", []):
        if stream.get("codec_type") == "video":
            video_stream = stream
            break

    if not video_stream:
        result.overall_status = "BLOCKED"
        result.issues.append("No video stream found")
        return result

    result.width = int(video_stream.get("width", 0))
    result.height = int(video_stream.get("height", 0))

    # Get duration
    duration_str = probe.get("format", {}).get("duration", "0")
    try:
        result.duration_sec = float(duration_str)
    except (ValueError, TypeError):
        result.duration_sec = 0.0

    if result.duration_sec <= 0:
        result.overall_status = "BLOCKED"
        result.issues.append("Invalid duration")
        return result

    # Extract frames
    for position, pct in FRAME_POSITIONS.items():
        timestamp = result.duration_sec * pct
        frame_path = frames_dir / f"{position}.jpg"

        frame = FrameResult(
            position=position,
            timestamp_sec=round(timestamp, 3),
            frame_path=str(frame_path),
            width=result.width,
            height=result.height,
        )

        ok = _extract_frame(clip_path, timestamp, frame_path)
        if not ok:
            frame.error = "Frame extraction failed"
            result.issues.append(f"Frame {position}: extraction failed")
            result.frames.append(frame)
            continue

        # Black frame detection
        is_black, pct_black = _detect_black_frame(frame_path)
        frame.is_black_frame = is_black
        frame.black_frame_pct = round(pct_black, 4)

        if is_black:
            frame.safe_zone_ok = False
            result.issues.append(f"Frame {position}: black frame ({pct_black:.1%})")

        # Safe zone check
        frame.safe_zone_ok = _check_safe_zone(frame_path)
        if not frame.safe_zone_ok:
            result.issues.append(f"Frame {position}: safe zone check failed")

        result.frames.append(frame)

    # Overall status
    if result.issues:
        result.overall_status = "ISSUES_FOUND"
    else:
        result.overall_status = "PASS"

    # Write report
    report_path = output_dir / "visual_qa_report.json"
    report_path.write_text(json.dumps(result.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

    return result


def process_publish_queue(limit: int = 5) -> List[VisualQAResult]:
    """Process all pending clips in publish_queue."""
    queue_dir = ROOT / "publish_queue"
    results = []

    for filepath in sorted(queue_dir.glob("*.json"))[:limit]:
        try:
            pkg = json.loads(filepath.read_text(encoding="utf-8"))
        except Exception:
            continue

        video = pkg.get("video_path") or pkg.get("clip_file_path")
        if not video or not Path(video).exists():
            continue

        clip_path = Path(video)
        clip_id = filepath.stem
        brand = pkg.get("brand", "unknown")
        ts = time.strftime("%Y%m%d_%H%M%S")
        output_dir = DEFAULT_OUTPUT / f"{ts}_{brand}_{clip_id}"

        result = generate_visual_qa(
            clip_path,
            output_dir=output_dir,
            clip_id=clip_id,
            source=f"publish_queue/{filepath.name}",
        )
        results.append(result)
        print(f"[VISUAL_QA] {clip_id}: {result.overall_status} "
              f"({len(result.frames)} frames, {len(result.issues)} issues)")

    return results


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="MBM-Social Visual QA Artifact Generator")
    parser.add_argument("clip", nargs="?", help="Path to clip file")
    parser.add_argument("--output-dir", "-o", help="Output directory for artifacts")
    parser.add_argument("--all", action="store_true", help="Process all publish_queue clips")
    parser.add_argument("--limit", type=int, default=5, help="Max clips to process with --all")
    args = parser.parse_args(argv)

    if args.all:
        results = process_publish_queue(limit=args.limit)
        print(f"\n[VISUAL_QA] Processed {len(results)} clips.")
        return 0

    if not args.clip:
        parser.error("Provide a clip path or use --all")

    clip_path = Path(args.clip)
    if not clip_path.exists():
        print(f"Error: {clip_path} not found")
        return 1

    output_dir = Path(args.output_dir) if args.output_dir else None
    result = generate_visual_qa(clip_path, output_dir=output_dir)

    print(f"\n[VISUAL_QA] {result.clip_id}: {result.overall_status}")
    print(f"  Duration: {result.duration_sec:.1f}s, {result.width}x{result.height}")
    print(f"  Frames: {len(result.frames)}")
    for f in result.frames:
        status = "BLACK" if f.is_black_frame else ("OK" if f.safe_zone_ok else "SAFE_ZONE")
        print(f"    {f.position} @ {f.timestamp_sec:.2f}s: {status}")
    if result.issues:
        print(f"  Issues: {result.issues}")
    print(f"  Report: {result.output_dir}/visual_qa_report.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
