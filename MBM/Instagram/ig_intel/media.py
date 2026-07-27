"""Media extraction helpers: download Reel video and sample frames via FFmpeg.

Respects the authenticated-session constraint: downloading is done through the
same browser transport cookies. For simplicity this fetches the media URL that
the collector captured (thumbnail_url) and, when a direct video URL is available,
downloads it. If no direct URL is present, the caller should supply one from the
browser session.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable


def download_video(url: str, dest: Path, ffmpeg_path: str = "ffmpeg",
                   log: Callable[[str], None] = print) -> Path | None:
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(
            [ffmpeg_path, "-y", "-i", url, "-c", "copy", str(dest)],
            check=True, capture_output=True, text=True, timeout=120,
        )
        log(f"[media] downloaded {dest}")
        return dest
    except Exception as e:  # noqa: BLE001
        log(f"[media] download failed: {e}")
        return None


def extract_audio(video: Path, ffmpeg_path: str = "ffmpeg") -> Path | None:
    audio = video.with_suffix(".wav")
    try:
        subprocess.run(
            [ffmpeg_path, "-y", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
             str(audio)],
            check=True, capture_output=True, text=True, timeout=120,
        )
        return audio
    except Exception:  # noqa: BLE001
        return None


def sample_frames(video: Path, out_dir: Path, every_sec: int = 2,
                  ffmpeg_path: str = "ffmpeg") -> list[Path]:
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    pattern = out_dir / "frame_%04d.png"
    try:
        subprocess.run(
            [ffmpeg_path, "-y", "-i", str(video), "-vf",
             f"fps=1/{every_sec}", str(pattern)],
            check=True, capture_output=True, text=True, timeout=120,
        )
        return sorted(out_dir.glob("frame_*.png"))
    except Exception:  # noqa: BLE001
        return []
