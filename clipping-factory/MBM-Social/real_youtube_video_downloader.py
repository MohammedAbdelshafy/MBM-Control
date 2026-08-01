"""
Real YouTube Video Downloader & 9:16 Vertical Renderer
======================================================
Mission: Downloads real viral YouTube videos for each channel using yt-dlp,
crops and reframes them to 9:16 (1080x1920) vertical format via ffmpeg, and saves real MP4 files.
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
VIDEOS_DIR = BASE_DIR / "generated_videos"
VIDEOS_DIR.mkdir(parents=True, exist_ok=True)

CHANNELS_SOURCES = [
    {
        "brand": "cutedosage",
        "search_query": "ytsearch3:cute puppy funny shorts",
        "title": "Cute Puppy Doing Funny Things | CuteDosage"
    },
    {
        "brand": "contech_ai",
        "search_query": "ytsearch3:ai voice agent cold calling shorts",
        "title": "AI Voice Agents Cold Calling Tech Revolution | Contech AI"
    },
    {
        "brand": "PlaqueBoyMax",
        "search_query": "ytsearch3:plaqueboymax funny moments shorts",
        "title": "PlaqueBoyMax Funniest Stream Highlights | PlaqueBoyMax"
    }
]


def download_and_crop_real_video(brand, search_query, title):
    print(f"\n[REAL VIDEO DOWNLOADER] Searching & Downloading for brand [{brand}]...")
    temp_raw = VIDEOS_DIR / f"raw_{brand}_{int(time.time())}.mp4"
    output_mp4 = VIDEOS_DIR / f"real_{brand}_{int(time.time())}.mp4"

    # 1. Download best video from YouTube search using yt-dlp
    dl_cmd = [
        "yt-dlp",
        "--no-playlist",
        "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "-o", str(temp_raw),
        search_query
    ]
    
    try:
        print(f"  - Executing yt-dlp search: '{search_query}'...")
        res = subprocess.run(dl_cmd, capture_output=True, text=True, timeout=120)
        
        if not temp_raw.exists():
            # Fallback direct download link if search timeout
            fallback_url = "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
            print(f"  - Using direct fallback clip: {fallback_url}...")
            dl_cmd_fallback = [
                "yt-dlp",
                "-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
                "-o", str(temp_raw),
                fallback_url
            ]
            subprocess.run(dl_cmd_fallback, capture_output=True, text=True, timeout=120)

    except Exception as e:
        print(f"  - Download exception: {e}")

    if not temp_raw.exists():
        print(f"  - Error: Raw video file could not be downloaded for {brand}.")
        return False

    # 2. Crop & Reframe to 9:16 vertical (1080x1920) via ffmpeg
    ff_cmd = [
        "ffmpeg", "-y",
        "-i", str(temp_raw),
        "-vf", "crop=ih*9/16:ih,scale=1080:1920",
        "-c:v", "libx264", "-preset", "fast", "-crf", "22",
        "-c:a", "aac", "-b:a", "192k",
        "-t", "20", # 20 second Short
        str(output_mp4)
    ]
    
    try:
        print(f"  - Cropping & Reframing to 1080x1920 9:16 vertical format via ffmpeg...")
        subprocess.run(ff_cmd, capture_output=True, text=True, timeout=120)
        
        if temp_raw.exists():
            temp_raw.unlink()
            
        if output_mp4.exists() and output_mp4.stat().st_size > 100000:
            size_mb = round(output_mp4.stat().st_size / (1024 * 1024), 2)
            print(f"  - SUCCESS: Rendered Real HD Video ({size_mb} MB) -> {output_mp4.name}")
            return str(output_mp4)

    except Exception as e:
        print(f"  - Crop exception: {e}")
        if temp_raw.exists():
            temp_raw.unlink()

    return False


def run_real_video_downloader():
    print("============================================================")
    print("[REAL VIDEO DOWNLOADER] DOWNLOADING REAL YOUTUBE CLIPS")
    print("============================================================")

    results = []
    for item in CHANNELS_SOURCES:
        res = download_and_crop_real_video(item["brand"], item["search_query"], item["title"])
        if res:
            results.append(res)

    print(f"\n[COMPLETE] Rendered {len(results)} Real 9:16 Vertical HD MP4 Videos!")


if __name__ == "__main__":
    run_real_video_downloader()
