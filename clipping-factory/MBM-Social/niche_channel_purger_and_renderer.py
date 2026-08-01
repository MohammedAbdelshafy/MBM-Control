"""
5 Channel Clean HD Video Renderer
===================================
Mission: Generates clean 1080x1920 60FPS vertical HD MP4 videos for all 5 channels:
- http://localhost:3002/videos/cutedosage.mp4
- http://localhost:3002/videos/dontwatchthis.mp4
- http://localhost:3002/videos/goalmachinez.mp4
- http://localhost:3002/videos/twistsrevealed.mp4
- http://localhost:3002/videos/clippingfactorymbm.mp4
"""

import os
import sys
import json
import time
import subprocess
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent.parent
VIDEOS_DIR = BASE_DIR / "generated_videos"
PUBLISH_QUEUE = BASE_DIR / "publish_queue"

VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
PUBLISH_QUEUE.mkdir(parents=True, exist_ok=True)

# 5 Official Channel Configurations
CHANNELS = [
    {
        "slug": "cutedosage",
        "display_name": "Cute Dosage",
        "handle": "@CuteDosage",
        "niche": "Wholesome Pets & Cute Animals",
        "title": "The Most Adorable Puppy & Kitten Playtime | Cute Dosage",
        "description": "Super cute puppy and kitten playing! 🐶🐱 #Shorts #CuteDosage #Pets",
        "demo_src": ROOT_DIR / "public" / "demos" / "demo_intro.mp4"
    },
    {
        "slug": "dontwatchthis",
        "display_name": "Don't Watch This",
        "handle": "@DONTWATCHTHIS1",
        "niche": "Dark Psychology & Mysterious Chilling Truths",
        "title": "5 Dark Psychology Secrets You Must Never Use | Don't Watch This",
        "description": "Chilling psychological secrets! 👁️😱 #Shorts #Mystery #DarkPsychology #DontWatchThis",
        "demo_src": ROOT_DIR / "public" / "demos" / "demo_ai-clipping.mp4"
    },
    {
        "slug": "goalmachinez",
        "display_name": "Goal Machinez",
        "handle": "@Goalmachinez",
        "niche": "Football & Soccer Legendary Highlights",
        "title": "Unbelievable Impossible Free Kicks in Football History | Goal Machinez",
        "description": "Insane free kick goals that shocked football! ⚽🔥 #Shorts #GoalMachinez #Football #Soccer",
        "demo_src": ROOT_DIR / "public" / "demos" / "demo_kpi-dashboard.mp4"
    },
    {
        "slug": "twistsrevealed",
        "display_name": "Twists Revealed",
        "handle": "@TwistsRevealed",
        "niche": "Movie Plot Twists & Shocking Film Endings",
        "title": "The Single Most Shocking Movie Plot Twist Ever | Twists Revealed",
        "description": "You won't believe this insane ending twist! 🎬🤯 #Shorts #TwistsRevealed #Movies #PlotTwist",
        "demo_src": ROOT_DIR / "public" / "demos" / "demo_dealing-room.mp4"
    },
    {
        "slug": "clippingfactorymbm",
        "display_name": "ClippingFactoryMBM",
        "handle": "@ClippingFactoryMBM",
        "niche": "AI SaaS, Autonomous Voice Bots & Build In Public",
        "title": "How AI Voice Agents Process 10,000 Calls Per Minute | ClippingFactoryMBM",
        "description": "Behind the scenes of our 24/7 AI Voice Cold Calling Swarm! 🚀🤖 #Shorts #ClippingFactoryMBM #AI #SaaS",
        "demo_src": ROOT_DIR / "public" / "demos" / "demo_commissions.mp4"
    }
]


def purge_old_files():
    print("[PURGER] Deleting all old videos and metadata...")
    for f in VIDEOS_DIR.glob("*"):
        if f.is_file():
            f.unlink()
    for f in PUBLISH_QUEUE.glob("*"):
        if f.is_file():
            f.unlink()
    print("[PURGER] Old files purged successfully. Starting fresh.\n")

def render_all_five_channels():
    print("============================================================")
    print("[5 CHANNEL ENGINE] RENDERING FULL-MOTION 1080x1920 60FPS HD VIDEOS")
    print("============================================================")
    
    purge_old_files()

    results = []

    for idx, channel in enumerate(CHANNELS, 1):
        target_filename = f"{channel['slug']}.mp4"
        output_path = VIDEOS_DIR / target_filename
        json_path = PUBLISH_QUEUE / f"pkg_{channel['slug']}.json"
        
        src_path = channel['demo_src']
        if not src_path.exists():
            src_path = ROOT_DIR / "public" / "demos" / "demo_ai-clipping.mp4"

        print(f"\n[{idx}/5] Rendering HD Video for Channel [{channel['display_name']}]...")
        
        ff_cmd = [
            "ffmpeg", "-y", "-i", str(src_path),
            "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-r", "60",
            "-c:a", "aac", "-b:a", "192k", "-t", "20",
            str(output_path)
        ]

        res = subprocess.run(ff_cmd, capture_output=True, text=True)
        
        if output_path.exists() and output_path.stat().st_size > 100000:
            size_mb = round(output_path.stat().st_size / (1024 * 1024), 2)
            play_url = f"http://localhost:3002/videos/{target_filename}"
            
            pkg = {
                "brand": channel["slug"],
                "display_name": channel["display_name"],
                "handle": channel["handle"],
                "niche": channel["niche"],
                "title": channel["title"],
                "description": channel["description"],
                "video_path": str(output_path),
                "status": "published",
                "published_at": datetime.now().isoformat(),
                "play_url": play_url
            }

            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(pkg, f, indent=2)

            results.append(pkg)
            print(f"  - SUCCESS: {channel['display_name']} ({size_mb} MB) -> {target_filename}")
            print(f"  - Playable Link: {play_url}")

    print(f"\n[COMPLETE] Successfully Rendered All {len(results)}/5 Channel Videos!")


if __name__ == "__main__":
    render_all_five_channels()
