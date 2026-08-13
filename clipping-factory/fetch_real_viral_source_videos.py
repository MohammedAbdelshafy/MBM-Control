"""
Real Viral Source Video Downloader (via yt-dlp)
===============================================
Harvests high-definition MP4 source videos for all 5 exact brand niches using yt-dlp:

Niches:
  1. Twists Revealed: Action & Thriller Movie Summaries & Plot Twists
  2. Cute Dosage: Cute Baby Videos & Heartwarming Moments
  3. Don't Watch This: Frightening Turkish Horror & Massive Breaking Ocean Waves
  4. Goal Machinez: High-Energy Football & Physics-Defying Goals
  5. Clipping Factory MBM: AI Agent Swarms & Business Automation

Run:
  python clipping-factory/fetch_real_viral_source_videos.py
"""

import os
import sys
import io
import json
import subprocess
from pathlib import Path
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BASE_DIR.parent
DEMOS_DIR = BASE_DIR / "MBM-Social" / "public" / "demos"
DEMOS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR = ROOT_DIR / "MBM" / "LeadEngine" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

TARGET_NICHES = [
    {
        "brand": "twistsrevealed",
        "niche": "Action & Thriller Movie Summaries & Plot Twists",
        "search": "ytsearch1:action thriller movie trailer HD",
        "filename": "real_action_thriller_source.mp4"
    },
    {
        "brand": "cutedosage",
        "niche": "Cute Baby Videos & Heartwarming Moments",
        "search": "ytsearch1:cute baby funny video short HD",
        "filename": "real_cute_baby_source.mp4"
    },
    {
        "brand": "dontwatchthis",
        "niche": "Turkish Horror Movie Summaries & Massive Ocean Waves",
        "search": "ytsearch1:giant ocean waves breaking HD",
        "filename": "real_horror_ocean_waves_source.mp4"
    },
    {
        "brand": "goalmachinez",
        "niche": "High-Energy Football & Physics-Defying Goals",
        "search": "ytsearch1:best football goals slow motion HD",
        "filename": "real_sports_football_goals_source.mp4"
    },
    {
        "brand": "clippingfactorymbm",
        "niche": "AI Agent Swarms & Video Clipping Automation",
        "search": "ytsearch1:AI technology digital automation HD",
        "filename": "real_ai_agents_automation_source.mp4"
    }
]


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[REAL YT HARVESTER 🎬] [{ts}] {msg}"
    print(line)
    try:
        with open(LOGS_DIR / "real_yt_source_downloads.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def download_with_ytdlp():
    log("==========================================================")
    log("  HARVESTING REAL HIGH-DEFINITION VIRAL VIDEOS VIA YT-DLP ")
    log("==========================================================")

    downloaded = []

    for item in TARGET_NICHES:
        target_path = DEMOS_DIR / item["filename"]
        log(f"📥 Harvesting HD Video for [{item['brand'].upper()}] ({item['niche']})...")

        cmd = [
            sys.executable, "-m", "yt_dlp",
            "--no-playlist",
            "-f", "b[ext=mp4]/b",
            "-o", str(target_path),
            item["search"]
        ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=180)
            if target_path.exists():
                size_mb = target_path.stat().st_size / (1024 * 1024)
                log(f"  ✅ Downloaded Real HD Source Video -> {target_path.name} ({size_mb:.2f} MB)")
                downloaded.append({
                    "brand": item["brand"],
                    "niche": item["niche"],
                    "filename": target_path.name,
                    "file_path": str(target_path),
                    "size_mb": round(size_mb, 2)
                })
            else:
                log(f"  ⚠️ yt-dlp notice for {item['brand']}: Output file not generated.")
        except Exception as e:
            log(f"  ⚠️ Download notice for {item['brand']}: {e}")

    summary = {
        "timestamp": datetime.now().isoformat(),
        "total_sources_harvested": len(downloaded),
        "target_audience": "STRICT US AUDIENCE (en-US)",
        "downloaded_sources": downloaded
    }

    out_file = LOGS_DIR / "real_yt_source_summary.json"
    out_file.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    log("==========================================================")
    log(f"✅ Successfully Harvested {len(downloaded)} Real Viral HD Source Videos!")
    log(f"  - Summary Log -> {out_file.name}")
    log("==========================================================")


if __name__ == "__main__":
    download_with_ytdlp()
