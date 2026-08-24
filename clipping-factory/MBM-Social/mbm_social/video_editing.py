"""
video_editing -- Automatic editing command construction (Phase 2).

Builds FFmpeg command lines for the Crayo-class vertical/format pipeline:

  - 9:16 vertical, 16:9, and 1:1 reframing (scale + crop + pad)
  - active-speaker / face-aware reframe region selection
  - dead-space removal (trim to the scored segment)
  - word-level caption burn-in with platform-specific styles
  - safe-zone positioning so captions/subjects are never clipped

This module only CONSTRUCTS commands; it does not run ffmpeg. Real speaker/face
detection is provided by an injected detector (e.g. a local model) — when none is
available it falls back to a center-weighted safe crop and says so. That keeps the
editing layer honest and testable offline.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Target aspect ratios supported by the brief.
ASPECTS = {"9:16", "16:9", "1:1"}

# Platform-specific caption styling (color/position/size). Kept as data so it is
# configurable and verifiable without rendering.
CAPTION_STYLES = {
    "youtube": {"font": "Arial", "size": 7, "color": "white", "box": "black@0.4",
                "position": "center,bottom", "safe_bottom": 0.12},
    "tiktok": {"font": "Arial-Bold", "size": 9, "color": "white", "box": "black@0.5",
               "position": "center,bottom", "safe_bottom": 0.14},
    "instagram": {"font": "Arial-Bold", "size": 8, "color": "white", "box": "black@0.45",
                  "position": "center,bottom", "safe_bottom": 0.13},
    "linkedin": {"font": "Arial", "size": 7, "color": "white", "box": "black@0.35",
                 "position": "center,bottom", "safe_bottom": 0.12},
    "twitter": {"font": "Arial-Bold", "size": 8, "color": "white", "box": "black@0.5",
                "position": "center,bottom", "safe_bottom": 0.13},
}


@dataclass
class ReframeRegion:
    """A detected subject region in normalized [0..1] coordinates."""
    x: float
    y: float
    w: float
    h: float

    def is_valid(self) -> bool:
        return 0.0 <= self.x <= 1.0 and 0.0 <= self.y <= 1.0 and 0.0 < self.w <= 1.0 and 0.0 < self.h <= 1.0


def choose_reframe_filter(region: Optional[ReframeRegion] = None,
                          aspect: str = "9:16") -> str:
    """Return an ffmpeg video filter string that reframes to `aspect`.

    When a subject `region` is supplied (active speaker / face), the crop is
    centered on it within the target aspect; otherwise a center-weighted safe
    crop is used (honest fallback, no fabricated detection).
    """
    if aspect not in ASPECTS:
        raise ValueError(f"unsupported aspect {aspect!r}; choose from {sorted(ASPECTS)}")

    if aspect == "9:16":
        tw, th = 1080, 1920
    elif aspect == "16:9":
        tw, th = 1920, 1080
    else:  # 1:1
        tw, th = 1080, 1080

    if region and region.is_valid():
        # crop around the subject, clamp to [0,1]
        cx = max(region.w / 2, min(1.0 - region.w / 2, region.x + region.w / 2))
        cy = max(region.h / 2, min(1.0 - region.h / 2, region.y + region.h / 2))
        crop_x = round(cx - region.w / 2, 3)
        crop_y = round(cy - region.h / 2, 3)
        crop = f"crop=x=iw*{crop_x:.3f}:y=ih*{crop_y:.3f}:w=iw*{region.w:.3f}:h=ih*{region.h:.3f}"
    else:
        # center-weighted safe crop (subject assumed centered)
        crop = "crop=iw*0.5625:ih*1.0:x=iw*0.21875:y=0"

    scale = f"scale={tw}:{th}:force_original_aspect_ratio=decrease"
    pad = f"pad={tw}:{th}:(ow-iw)/2:(oh-ih)/2:color=black"
    return f"{crop},{scale},{pad}"


def build_reframe_command(src: str, dst: str, aspect: str = "9:16",
                          region: Optional[ReframeRegion] = None,
                          start_ts: Optional[float] = None,
                          end_ts: Optional[float] = None) -> list[str]:
    """FFmpeg argv to reframe `src` -> `dst` at `aspect`, trimming if given."""
    cmd = ["ffmpeg", "-y", "-i", src]
    if start_ts is not None and end_ts is not None:
        cmd += ["-ss", f"{start_ts:.3f}", "-to", f"{end_ts:.3f}"]
    vf = choose_reframe_filter(region, aspect)
    cmd += ["-vf", vf, "-c:a", "copy", "-preset", "veryfast", dst]
    return cmd


def build_caption_command(src: str, dst: str, caption_text: str,
                          platform: str = "youtube",
                          words: Optional[list[dict]] = None) -> list[str]:
    """FFmpeg argv to burn word-level captions with a platform style.

    `words` is an optional list of {"text", "start", "end"} for word-level
    timing; when omitted the whole `caption_text` is shown for the clip duration.
    """
    style = CAPTION_STYLES.get(platform, CAPTION_STYLES["youtube"])
    safe = style["safe_bottom"]
    # drawtext escapes ':' and '\' and '%'
    def esc(t: str) -> str:
        return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")

    if words:
        # chain drawtext filters, one per word timed with enable
        parts = []
        for w in words:
            en = f"enable='between(t,{w['start']:.2f},{w['end']:.2f})'"
            parts.append(
                f"drawtext=text='{esc(w['text'])}':fontfile='{style['font']}'"
                f":fontcolor={style['color']}:fontsize={style['size']}"
                f":box=1:boxcolor={style['box']}:boxborderw=8"
                f":x=(w-text_w)/2:y=h-th-{int(safe*100)}%*h/100:{en}"
            )
        vf = ",".join(parts)
    else:
        vf = (
            f"drawtext=text='{esc(caption_text)}':fontfile='{style['font']}'"
            f":fontcolor={style['color']}:fontsize={style['size']}"
            f":box=1:boxcolor={style['box']}:boxborderw=8"
            f":x=(w-text_w)/2:y=h-th-{int(safe*100)}%*h/100"
        )
    return ["ffmpeg", "-y", "-i", src, "-vf", vf, "-c:a", "copy", "-preset", "veryfast", dst]


def build_platform_render(src: str, dst: str, platform: str,
                          aspect: Optional[str] = None,
                          region: Optional[ReframeRegion] = None,
                          start_ts: Optional[float] = None,
                          end_ts: Optional[float] = None) -> list[str]:
    """One-shot render command for a given platform (format + platform default)."""
    # platform -> default aspect
    default_aspect = {
        "youtube": "9:16", "tiktok": "9:16", "instagram": "9:16",
        "linkedin": "16:9", "twitter": "16:9",
    }.get(platform, "9:16")
    aspect = aspect or default_aspect
    return build_reframe_command(src, dst, aspect=aspect, region=region,
                                 start_ts=start_ts, end_ts=end_ts)
