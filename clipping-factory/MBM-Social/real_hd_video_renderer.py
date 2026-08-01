"""
Real HD Video Content & Motion Converter (NO STATIC/OLD DEMO IMAGES)
======================================================================
Mission: Converts real viral video clips (sourced from TikTok, Instagram, YouTube, and Facebook)
into 1080x1920 60FPS vertical Shorts & Reels format.
Strict Rule: ZERO static 2-month old project images or demo files.
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent.parent
VIRAL_POOL_DIR = BASE_DIR / "viral_pool"
VIDEOS_DIR = BASE_DIR / "generated_videos"
PUBLISH_QUEUE = BASE_DIR / "publish_queue"
MEDIA_DIR = PUBLISH_QUEUE / "media"

VIRAL_POOL_DIR.mkdir(parents=True, exist_ok=True)
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
MEDIA_DIR.mkdir(parents=True, exist_ok=True)


def get_real_viral_video_pool():
    """Fetches list of active viral video clips from viral_pool."""
    clips = list(VIRAL_POOL_DIR.glob("*.mp4"))
    if not clips:
        # Run harvester on the fly if pool is empty
        try:
            from viral_video_harvester import run_viral_harvester
            run_viral_harvester()
            clips = list(VIRAL_POOL_DIR.glob("*.mp4"))
        except Exception:
            pass
    return clips


def convert_source_to_916_short(source_mp4, output_mp4):
    """Reframes a real high-definition MP4 video file into 1080x1920 vertical format with anti-flag filters."""
    video_filter = (
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        "setpts=0.97*PTS,"
        "unsharp=5:5:1.0:5:5:0.0,"
        "eq=contrast=1.15:brightness=0.02:saturation=1.25"
    )
    audio_filter = "asetrate=44100*1.03,aresample=44100,loudnorm=I=-14:LRA=11:TP=-1.5"

    ff_cmd = [
        "ffmpeg", "-y",
        "-i", str(source_mp4),
        "-vf", video_filter,
        "-af", audio_filter,
        "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-r", "60",
        "-c:a", "aac", "-b:a", "192k",
        "-t", "15",
        str(output_mp4)
    ]
    try:
        res = subprocess.run(ff_cmd, capture_output=True, text=True, timeout=60)
        return output_mp4.exists() and output_mp4.stat().st_size > 50000
    except Exception as e:
        return False


def run_real_hd_video_renderer():
    print("============================================================")
    print("[REAL VIRAL CONTENT ENGINE] REFRAMING VIRAL TIKTOK/INSTAGRAM CLIPS")
    print("============================================================")

    viral_pool = get_real_viral_video_pool()
    if not viral_pool:
        print("[!] Warning: No viral clips found in pool. Harvesting now...")
        return

    # 1. Process all files in generated_videos
    gen_files = list(VIDEOS_DIR.glob("*.mp4"))
    print(f"[REAL VIRAL ENGINE] Found {len(gen_files)} files in generated_videos.")

    converted_count = 0

    for idx, target_file in enumerate(gen_files):
        # Pick real viral clip in round-robin from viral_pool
        src_video = viral_pool[idx % len(viral_pool)]
        print(f"\n[{idx+1}/{len(gen_files)}] Reframing Real Viral Clip '{src_video.name}' -> '{target_file.name}'...")
        
        success = convert_source_to_916_short(src_video, target_file)
        if success:
            size_mb = round(target_file.stat().st_size / (1024 * 1024), 2)
            converted_count += 1
            print(f"  - SUCCESS: Converted Real Viral Video ({size_mb} MB) -> {target_file.name}")

    # 2. Process media directory
    media_files = list(MEDIA_DIR.glob("*.mp4"))
    for idx, target_file in enumerate(media_files):
        src_video = viral_pool[idx % len(viral_pool)]
        convert_source_to_916_short(src_video, target_file)

    print(f"\n[COMPLETE] Converted {converted_count} Real High-Definition 1080x1920 MP4 Videos from Viral Pool!")


if __name__ == "__main__":
    run_real_hd_video_renderer()
