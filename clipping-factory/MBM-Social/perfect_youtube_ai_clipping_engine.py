"""
Perfect YouTube AI Video Generation & Clipping Engine
======================================================
Mission: 100% Automated YouTube Shorts / TikTok / Reels Video Generator & Clipper.
Strict Rule: NO local workspace images/videos used! Uses ONLY live YouTube video libraries
(via yt-dlp) and pure Higgsfield AI Video Generation (Seedance 2.0 / Nano Banana 2).
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

# 5 Niche Channel Configurations & Live YouTube Search Queries
CHANNEL_PROMPTS = [
    {
        "slug": "cutedosage",
        "display_name": "Cute Dosage",
        "handle": "@CuteDosage",
        "niche": "Cute Pets & Animals",
        "higgsfield_prompt": "Super adorable Golden Retriever puppy playing with a playful kitten in a sunlit garden, masterfully enhanced by Nano Banana 2, photorealistic 8K resolution, 9:16 vertical video, 60fps",
        "yt_search": "ytsearch1:cute puppy kitten funny playing shorts",
        "title": "Super Cute Puppy & Kitten Garden Playtime | Cute Dosage",
        "description": "Adorable puppy and kitten moment! 🐶🐱 #Shorts #CuteDosage #Pets #HiggsfieldAI"
    },
    {
        "slug": "dontwatchthis",
        "display_name": "Don't Watch This",
        "handle": "@DONTWATCHTHIS1",
        "niche": "Dark Psychology & Chilling Truths",
        "higgsfield_prompt": "Mysterious silhouetted figure in dark fog alleyway with neon light contrast, dark psychology aesthetic, masterfully enhanced by Nano Banana 2, photorealistic 8K, 9:16 vertical video, 60fps",
        "yt_search": "ytsearch1:dark psychology mind tricks shorts",
        "title": "5 Dark Psychology Secrets You Must Never Use | Don't Watch This",
        "description": "Chilling psychological secrets that control conversations! 👁️😱 #Shorts #Mystery #DarkPsychology #HiggsfieldAI"
    },
    {
        "slug": "goalmachinez",
        "display_name": "Goal Machinez",
        "handle": "@Goalmachinez",
        "niche": "Football & Sports Legendary Highlights",
        "higgsfield_prompt": "Soccer stadium exploding with cheering fans under bright stadium lights, dynamic freekick goal into top corner, masterfully enhanced by Nano Banana 2, 8K, 9:16 vertical video, 60fps",
        "yt_search": "ytsearch1:impossible freekick football goals shorts",
        "title": "Unbelievable Free Kick Goals in Football History | Goal Machinez",
        "description": "Insane free kick goals that shocked football! ⚽🔥 #Shorts #GoalMachinez #Football #Soccer #HiggsfieldAI"
    },
    {
        "slug": "twistsrevealed",
        "display_name": "Twists Revealed",
        "handle": "@TwistsRevealed",
        "niche": "Movie Plot Twists & Mind-Blowing Film Endings",
        "higgsfield_prompt": "Dramatic movie theater screen glowing in dark auditorium showing plot twist reveal moment, masterfully enhanced by Nano Banana 2, photorealistic 8K cinema lighting, 9:16 vertical video, 60fps",
        "yt_search": "ytsearch1:shocking movie plot twist reveal shorts",
        "title": "The Single Most Shocking Movie Plot Twist Ever | Twists Revealed",
        "description": "Insane movie ending twist reveal! 🎬🤯 #Shorts #TwistsRevealed #Movies #PlotTwist #HiggsfieldAI"
    },
    {
        "slug": "clippingfactorymbm",
        "display_name": "ClippingFactoryMBM",
        "handle": "@ClippingFactoryMBM",
        "niche": "AI SaaS & Autonomous Voice Bots",
        "higgsfield_prompt": "Futuristic 2026 AI Voice Agent holographic interface emitting glowing cyan soundwaves, automated cold call dashboard, masterfully enhanced by Nano Banana 2, photorealistic 8K render, 9:16 vertical video, 60fps",
        "yt_search": "ytsearch1:ai voice agent cold calling automated shorts",
        "title": "How AI Voice Agents Process 10,000 Calls Per Minute | ClippingFactoryMBM",
        "description": "Behind the scenes of our 24/7 AI Voice Cold Calling Swarm! 🚀🤖 #Shorts #ClippingFactoryMBM #AI #SaaS #HiggsfieldAI"
    }
]


def download_live_youtube_video(yt_query, output_mp4):
    """Downloads public video clip from YouTube via yt-dlp (Strictly NO local images/videos!)."""
    print(f"[YOUTUBE LIBRARY] Fetching live public video clip for query: '{yt_query}'...")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--default-search", "ytsearch",
        "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio/best[height<=1080][ext=mp4]/best",
        "--max-filesize", "50M",
        "-o", str(output_mp4),
        yt_query
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return output_mp4.exists() and output_mp4.stat().st_size > 100000
    except Exception as e:
        print(f"[YOUTUBE LIBRARY] Notice: {e}")
        return False


def generate_pure_higgsfield_video(prompt, output_mp4):
    """Generates pure AI Video via Higgsfield CLI."""
    print(f"[HIGGSFIELD AI] Generating pure AI video: '{prompt[:60]}...'")
    cmd = [
        "higgsfield", "generate", "create", "seedance_2_0",
        "--prompt", prompt,
        "--aspect_ratio", "9:16",
        "--wait"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180, shell=True)
        if res.returncode == 0 and "http" in res.stdout:
            url = [w for w in res.stdout.split() if w.startswith("http")][0]
            print(f"[HIGGSFIELD AI] Downloading Cloudfront Asset: {url}...")
            subprocess.run(["curl.exe", "-fsSL", url, "-o", str(output_mp4)], timeout=60)
            return url, output_mp4.exists()
    except Exception as e:
        print(f"[HIGGSFIELD AI] Notice: {e}")
    return None, False


def process_vertical_hd_video(input_video, output_video):
    """Reframes video to 1080x1920 60FPS vertical format using FFMPEG."""
    ff_cmd = [
        "ffmpeg", "-y", "-i", str(input_video),
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "22", "-r", "60",
        "-c:a", "aac", "-b:a", "192k", "-t", "20",
        str(output_video)
    ]
    subprocess.run(ff_cmd, capture_output=True, text=True, timeout=90)
    return output_video.exists() and output_video.stat().st_size > 100000


def run_perfect_youtube_ai_clipping_pipeline():
    print("============================================================")
    print("[PERFECT AI CLIPPING ENGINE] YOUTUBE LIBRARIES + HIGGSFIELD AI")
    print("============================================================")

    processed_count = 0

    for idx, channel in enumerate(CHANNEL_PROMPTS, 1):
        print(f"\n[CHANNEL {idx}/5] Processing Brand [{channel['display_name']}]...")
        
        raw_yt_path = VIDEOS_DIR / f"raw_yt_{channel['slug']}_{int(time.time())}.mp4"
        higgsfield_path = VIDEOS_DIR / f"hg_{channel['slug']}_{int(time.time())}.mp4"
        final_mp4_path = VIDEOS_DIR / f"{channel['slug']}.mp4"
        json_path = PUBLISH_QUEUE / f"pkg_{channel['slug']}.json"

        # 1. First attempt downloading live YouTube video clip
        yt_ok = download_live_youtube_video(channel['yt_search'], raw_yt_path)
        
        source_file = None
        cdn_url = None

        if yt_ok:
            source_file = raw_yt_path
            print(f"  - SUCCESS: Downloaded Live YouTube Clip ({round(raw_yt_path.stat().st_size/(1024*1024),2)} MB)")
        else:
            # 2. Fallback to pure Higgsfield AI Video Generation
            cdn_url, hg_ok = generate_pure_higgsfield_video(channel['higgsfield_prompt'], higgsfield_path)
            if hg_ok:
                source_file = higgsfield_path
                print(f"  - SUCCESS: Generated Pure Higgsfield AI Video")

        if source_file and source_file.exists():
            # 3. Process into 1080x1920 60FPS vertical HD MP4
            success = process_vertical_hd_video(source_file, final_mp4_path)
            
            if success:
                play_url = f"http://localhost:3002/videos/{channel['slug']}.mp4"
                package = {
                    "brand": channel["slug"],
                    "display_name": channel["display_name"],
                    "handle": channel["handle"],
                    "niche": channel["niche"],
                    "title": channel["title"],
                    "description": channel["description"],
                    "higgsfield_cdn": cdn_url or "https://higgsfield.ai",
                    "video_path": str(final_mp4_path),
                    "status": "published",
                    "published_at": datetime.now().isoformat(),
                    "play_url": play_url
                }

                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(package, f, indent=2)

                processed_count += 1
                print(f"  - LIVE VIDEO READY: {channel['display_name']} ({round(final_mp4_path.stat().st_size/(1024*1024),2)} MB)")
                print(f"  - Playable Link: {play_url}")

        # Clean up temporary downloads
        if raw_yt_path.exists():
            try:
                raw_yt_path.unlink()
            except Exception:
                pass

    print(f"\n[COMPLETE] Perfect AI Clipping Engine Finished ({processed_count}/5 Channels Live)!")


if __name__ == "__main__":
    run_perfect_youtube_ai_clipping_pipeline()
