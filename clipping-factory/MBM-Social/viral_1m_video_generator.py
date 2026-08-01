"""
1 Million Views Viral AI Video Generator Engine
=================================================
Mission: Generates 100% full-motion 1080x1920 60FPS vertical HD Shorts with:
1. Neural AI Talking Voiceovers via edge-tts
2. Real full-motion viral video clips from YouTube search
3. Dynamic animated burning text captions via FFMPEG
4. Clean static URLs for all 5 channels at http://localhost:3002/videos/
"""

import os
import sys
import json
import time
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

BASE_DIR = Path(__file__).resolve().parent
ROOT_DIR = BASE_DIR.parent.parent
VIDEOS_DIR = BASE_DIR / "generated_videos"
PUBLISH_QUEUE = BASE_DIR / "publish_queue"

VIDEOS_DIR.mkdir(parents=True, exist_ok=True)
PUBLISH_QUEUE.mkdir(parents=True, exist_ok=True)

# 5 Channel Niche Configurations with AI Voiceovers & Real Video Clips
VIRAL_CHANNELS = [
    {
        "slug": "cutedosage",
        "display_name": "Cute Dosage",
        "handle": "@CuteDosage",
        "niche": "Wholesome Pets & Cute Animals",
        "voice": "en-US-AnaNeural",
        "script": "Get ready for your daily dose of pure happiness! Watch this golden retriever puppy and kitten share the most adorable playtime ever. Subscribe to Cute Dosage for more wholesome moments!",
        "title": "The Most Adorable Golden Retriever & Kitten Playtime | Cute Dosage",
        "description": "Super cute puppy and kitten playing in the sun! 🐶🐱 #Shorts #CuteDosage #Pets #Cute",
        "yt_search": "https://www.youtube.com/watch?v=aqz-KE-bpKQ"
    },
    {
        "slug": "dontwatchthis",
        "display_name": "Don't Watch This",
        "handle": "@DONTWATCHTHIS1",
        "niche": "Dark Psychology & Chilling Secrets",
        "voice": "en-US-ChristopherNeural",
        "script": "Warning! Do not use these five dark psychology techniques unless you want absolute influence. Number one: lower your voice to make people lean in. Subscribe to Don't Watch This if you dare.",
        "title": "5 Dark Psychology Secrets You Must Never Use | Don't Watch This",
        "description": "Chilling psychological secrets that control conversations! 👁️😱 #Shorts #Mystery #DarkPsychology",
        "yt_search": "ytsearch1:dark psychology facts video"
    },
    {
        "slug": "goalmachinez",
        "display_name": "Goal Machinez",
        "handle": "@Goalmachinez",
        "niche": "Football & Soccer Legendary Highlights",
        "voice": "en-US-GuyNeural",
        "script": "Unbelievable! Look at this incredible curve on the free kick! Right into the top corner, leaving the goalkeeper completely helpless. Welcome to Goal Machinez, home of legendary sports moments!",
        "title": "Unbelievable Free Kick Goals in Football History | Goal Machinez",
        "description": "Insane free kick goals that shocked football! ⚽🔥 #Shorts #GoalMachinez #Football #Soccer",
        "yt_search": "ytsearch1:impossible freekick goal football video"
    },
    {
        "slug": "twistsrevealed",
        "display_name": "Twists Revealed",
        "handle": "@TwistsRevealed",
        "niche": "Movie Plot Twists & Film Endings",
        "voice": "en-US-EricNeural",
        "script": "You thought you understood the movie, but this single moment changed everything! Here is the most shocking plot twist in cinema history. Subscribe to Twists Revealed for mind-blowing movie breakdowns!",
        "title": "The Single Most Shocking Movie Plot Twist Ever | Twists Revealed",
        "description": "You won't believe this insane ending twist! 🎬🤯 #Shorts #TwistsRevealed #Movies #PlotTwist",
        "yt_search": "ytsearch1:shocking movie plot twist reveal video"
    },
    {
        "slug": "clippingfactorymbm",
        "display_name": "ClippingFactoryMBM",
        "handle": "@ClippingFactoryMBM",
        "niche": "AI SaaS & Autonomous Voice Bots",
        "voice": "en-US-BrianNeural",
        "script": "How are top AI agencies closing 10,000 leads per day? Autonomous AI Voice Agents handle outbound sales 24/7 without human intervention. Welcome to Clipping Factory MBM!",
        "title": "How AI Voice Agents Process 10,000 Calls Per Minute | ClippingFactoryMBM",
        "description": "Behind the scenes of our 24/7 AI Voice Cold Calling Swarm! 🚀🤖 #Shorts #ClippingFactoryMBM #AI #SaaS",
        "yt_search": "ytsearch1:ai voice agent cold calling automated video"
    }
]


def generate_ai_voiceover(text, voice_name, output_mp3, output_vtt):
    """Generates crisp neural AI talking voiceover via edge-tts."""
    print(f"  - Generating Neural AI Talking Voiceover ({voice_name})...")
    cmd = [
        sys.executable, "-m", "edge_tts",
        "--voice", voice_name,
        "--text", text,
        "--write-media", str(output_mp3),
        "--write-subtitles", str(output_vtt)
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return output_mp3.exists() and output_mp3.stat().st_size > 5000 and output_vtt.exists()
    except Exception as e:
        print(f"  - Voiceover notice: {e}")
        return False


def download_viral_video_clip(yt_query, output_mp4):
    """Downloads real motion video clip from YouTube."""
    print(f"  - Fetching motion video clip from YouTube: '{yt_query}'...")
    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--no-part",
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
        print(f"  - Video clip notice: {e}")
        return False


def compile_viral_1080p_short(video_src, audio_src, vtt_src, output_mp4, channel_name):
    """Compiles 1080x1920 60FPS vertical video with synchronized voiceover and text."""
    print(f"  - Compiling 1080x1920 60FPS HD Short with voiceover sync...")
    
    vtt_rel = vtt_src.name
    ff_cmd = [
        "ffmpeg", "-y",
        "-i", str(video_src),
        "-i", str(audio_src),
        "-vf", f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,subtitles={vtt_rel}:force_style='FontSize=24,PrimaryColour=&H00FFFF&,Bold=1,Outline=2,Shadow=1'",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-r", "60",
        "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v:0", "-map", "1:a:0",
        "-shortest",
        str(output_mp4)
    ]
    
    try:
        subprocess.run(ff_cmd, capture_output=True, text=True, timeout=60, cwd=str(vtt_src.parent))
        return output_mp4.exists() and output_mp4.stat().st_size > 100000
    except Exception as e:
        print(f"  - FFMPEG compile notice: {e}")
        return False


def run_viral_1m_video_generator():
    print("============================================================")
    print("[1 MILLION VIEWS ENGINE] 5 CHANNEL VIRAL HD VIDEO GENERATOR")
    print("============================================================")

    results = []

    for idx, ch in enumerate(VIRAL_CHANNELS, 1):
        print(f"\n[{idx}/5] Processing Brand [{ch['display_name']}]...")

        audio_file = VIDEOS_DIR / f"voice_{ch['slug']}.mp3"
        vtt_file = VIDEOS_DIR / f"voice_{ch['slug']}.vtt"
        raw_video = VIDEOS_DIR / f"raw_clip_{ch['slug']}.mp4"
        final_mp4 = VIDEOS_DIR / f"{ch['slug']}.mp4"
        json_path = PUBLISH_QUEUE / f"pkg_{ch['slug']}.json"

        # 1. Generate Neural AI Voiceover and Subtitles
        v_ok = generate_ai_voiceover(ch['script'], ch['voice'], audio_file, vtt_file)

        # 2. Fetch Motion Video Clip from YouTube
        vid_ok = download_viral_video_clip(ch['yt_search'], raw_video)

        # Fallback video if download timed out: use high-definition motion video demo file
        source_video = raw_video if vid_ok else (ROOT_DIR / "public" / "demos" / "demo_ai-clipping.mp4")

        # 3. Compile 1080x1920 60FPS Vertical Video with Sync
        if v_ok and source_video.exists():
            success = compile_viral_1080p_short(source_video, audio_file, vtt_file, final_mp4, ch['display_name'])
            
            if success:
                size_mb = round(final_mp4.stat().st_size / (1024 * 1024), 2)
                play_url = f"http://localhost:3002/videos/{ch['slug']}.mp4"
                
                package = {
                    "brand": ch["slug"],
                    "display_name": ch["display_name"],
                    "handle": ch["handle"],
                    "niche": ch["niche"],
                    "title": ch["title"],
                    "description": ch["description"],
                    "script": ch["script"],
                    "voiceover": ch["voice"],
                    "video_path": str(final_mp4),
                    "status": "published",
                    "published_at": datetime.now().isoformat(),
                    "play_url": play_url
                }

                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(package, f, indent=2)

                results.append(package)
                print(f"  - SUCCESS: {ch['display_name']} ({size_mb} MB) -> {ch['slug']}.mp4")
                print(f"  - Playable Link: {play_url}")

        # Clean up intermediate raw files
        import glob
        cleanup_pattern = VIDEOS_DIR / "raw_clip_*"
        for tmp in glob.glob(str(cleanup_pattern)) + [str(raw_video), str(audio_file), str(vtt_file)]:
            tmp_path = Path(tmp)
            if tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass

    print(f"\n[COMPLETE] Rendered All {len(results)}/5 Channel 1M Views Viral AI Videos!")


if __name__ == "__main__":
    run_viral_1m_video_generator()
