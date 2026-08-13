"""
Cinematic Movie Recap & Suspense Story Shorts Engine
=====================================================
Mission: Generates exact high-suspense movie recap Shorts matching the style of:
1. "A Bored Teen Spies On His Neighbor For Fun, Until He Witnesses A Murder" (ztngkE7hviY)
2. "A Group of Strangers Board a Flight, Unaware the Pilot Invited Them for One Final Revenge" (8lsaPNa5cH8)

Components:
- Suspenseful Neural Voiceover via edge-tts (en-US-ChristopherNeural / en-US-EricNeural)
- Real high-paced movie thriller cuts via yt-dlp
- High-contrast animated yellow/white centered subtitle overlays
- Cinematic AI sharpness & EBU R128 audio normalization
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


# Dynamically build RECAP_STORIES from BrandRegistry.json
import json
from pathlib import Path

def load_brand_registry():
    # Primary location: same directory as this script
    registry_path = Path(__file__).resolve().parent / "BrandRegistry.json"
    # Fallback: one level up inside MBM-Social (in case of moved script)
    if not registry_path.is_file():
        registry_path = Path(__file__).resolve().parent.parent / "MBM-Social" / "BrandRegistry.json"
    with open(registry_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("brands", {})

def build_recap_stories():
    stories = []
    brands = load_brand_registry()
    for slug, cfg in brands.items():
        if not cfg.get("active"):
            continue
        # Preserve custom entries for known brands
        if slug in {"twistsrevealed", "dontwatchthis"}:
            continue
        # Default fallback values for other brands
        stories.append({
            "slug": slug,
            "display_name": cfg.get("display_name", slug.title()),
            "handle": cfg.get("handle", f"@{slug}"),
            "voice": "en-US-ChristopherNeural",
            "script": f"Dynamic AI short for {cfg.get('display_name', slug.title())}",
            "title": f"{cfg.get('display_name', slug.title())} – AI‑Generated Short",
            "description": f"{cfg.get('display_name', slug.title())} short generated automatically by the cinematic recap engine.",
            "yt_query": None
        })
    # Append the two custom brand definitions (unchanged from original)
    stories.extend([
        {
            "slug": "twistsrevealed",
            "display_name": "Twists Revealed",
            "handle": "@TwistsRevealed",
            "voice": "en-US-ChristopherNeural",
            "script": "A bored teenager decides to spy on his neighbor with binoculars just for fun. But tonight, he witnesses a cold-blooded murder through the window. Now the killer turns around and looks directly into his camera lens. Subscribe to Twists Revealed!",
            "title": "He Spied On His Neighbor... Until He Witnessed A Murder No One Believes",
            "description": "Chilling movie recap story! 🎬😱 #Shorts #TwistsRevealed #MovieRecap #Thriller #PlotTwist",
            "yt_query": "https://youtu.be/ztngkE7hviY"
        },
        {
            "slug": "dontwatchthis",
            "display_name": "Don't Watch This",
            "handle": "@DONTWATCHTHIS1",
            "voice": "en-US-EricNeural",
            "script": "Twelve strangers board a night flight to London, thinking it's just a normal journey. But mid-flight, the pilot locks the cabin doors and makes an announcement: he invited them all here to execute his final revenge. Subscribe to Don't Watch This!",
            "title": "A Group of Strangers Board a Flight, Unaware the Pilot Invited Them for Revenge",
            "description": "Chilling flight revenge story recap! ✈️😱 #Shorts #DontWatchThis #MovieRecap #Suspense #DarkStory",
            "yt_query": "https://youtu.be/8lsaPNa5cH8"
        }
    ])
    return stories

RECAP_STORIES = build_recap_stories()


def download_recap_movie_clip(yt_url, output_mp4):
    """Downloads public video stream from YouTube.
    Returns True if a valid file >100KB was saved, otherwise False.
    """
    if not yt_url:
        print("  - No YouTube URL provided, using demo fallback.")
        return False
    print(f"  - Fetching YouTube source stream: {yt_url}...")
    cmd = [
        "yt-dlp", "--no-playlist",
        "-f", "bestvideo[height<=1080][ext=mp4]+bestaudio/best[height<=1080][ext=mp4]/best",
        "--max-filesize", "50M",
        "-o", str(output_mp4),
        yt_url
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
        return output_mp4.exists() and output_mp4.stat().st_size > 100000
    except Exception as e:
        print(f"  - Download notice: {e}")
        return False


def generate_suspense_voiceover(script, voice, output_mp3, output_vtt=None):
    """Generates deep suspenseful narration via edge-tts with timed subtitles."""
    print(f"  - Generating Suspenseful Narration ({voice})...")
    cmd = [
        sys.executable, "-m", "edge_tts",
        "--voice", voice,
        "--text", script,
        "--write-media", str(output_mp3)
    ]
    if output_vtt:
        cmd.extend(["--write-subtitles", str(output_vtt)])
    try:
        subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return output_mp3.exists() and output_mp3.stat().st_size > 5000
    except Exception as e:
        print(f"  - Voiceover notice: {e}")
        return False


def compile_recap_short(video_input, audio_input, output_mp4, title_overlay, vtt_input=None):
    """Compiles 1080x1920 60FPS vertical movie recap short with filters and captions."""
    print(f"  - Compiling 1080x1920 60FPS Cinematic Movie Recap Short...")
    
    vf = (
        "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,"
        "unsharp=5:5:1.0:5:5:0.0,"
        "eq=contrast=1.18:brightness=0.01:saturation=1.25"
    )
    if vtt_input and Path(vtt_input).exists():
        vtt_rel = Path(vtt_input).name
        vf += f",subtitles='{vtt_rel}':force_style='FontSize=18,PrimaryColour=&H00FFFF&,Bold=1,Outline=2,Shadow=1,Alignment=2,MarginV=120,MarginL=60,MarginR=60'"

    af = "loudnorm=I=-14:LRA=11:TP=-1.5"

    ff_cmd = [
        "ffmpeg", "-y",
        "-i", str(video_input),
        "-i", str(audio_input),
        "-vf", vf,
        "-af", af,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "18", "-r", "60",
        "-c:a", "aac", "-b:a", "192k",
        "-map", "0:v:0", "-map", "1:a:0",
        "-shortest",
        str(output_mp4)
    ]

    try:
        cwd_dir = str(Path(vtt_input).parent) if vtt_input and Path(vtt_input).exists() else None
        subprocess.run(ff_cmd, capture_output=True, text=True, timeout=90, cwd=cwd_dir)
        return output_mp4.exists() and output_mp4.stat().st_size > 100000
    except Exception as e:
        print(f"  - FFMPEG recap compile notice: {e}")
        return False


def run_cinematic_movie_recap_pipeline():
    print("============================================================")
    print("[CINEMATIC MOVIE RECAP ENGINE] HIGH-SUSPENSE RECAP SHORTS")
    print("============================================================")

    for ch in RECAP_STORIES:
        print(f"\nProcessing Movie Recap for Brand [{ch['display_name']}]...")
        raw_yt = VIDEOS_DIR / f"raw_recap_{ch['slug']}.mp4"
        voice_mp3 = VIDEOS_DIR / f"voice_recap_{ch['slug']}.mp3"
        voice_vtt = VIDEOS_DIR / f"voice_recap_{ch['slug']}.vtt"
        final_mp4 = VIDEOS_DIR / f"{ch['slug']}.mp4"
        json_path = PUBLISH_QUEUE / f"pkg_{ch['slug']}.json"

        # 1. Download YouTube source clip
        dl_ok = download_recap_movie_clip(ch['yt_query'], raw_yt)
        source = raw_yt if dl_ok else (ROOT_DIR / "public" / "demos" / "demo_ai-clipping.mp4")

        # 1.5 Optimize prompts using high-view benchmark comparison via Web API (Gemini)
        from prompt_optimizer import optimize_prompt
        theme_query = f"{ch['display_name']} shorts"
        ch['script'], ch['title'], ch['description'] = optimize_prompt(
            ch['slug'], 
            theme_query, 
            ch['script'], 
            ch['title'], 
            ch['description']
        )

        # 2. Generate suspense voiceover with subtitles
        v_ok = generate_suspense_voiceover(ch['script'], ch['voice'], voice_mp3, voice_vtt)

        # 3. Compile high-suspense 1080x1920 Short
        if v_ok and source.exists():
            success = compile_recap_short(source, voice_mp3, final_mp4, ch['title'], voice_vtt)
            if success:
                size_mb = round(final_mp4.stat().st_size / (1024 * 1024), 2)
                play_url = f"http://localhost:3002/videos/{ch['slug']}.mp4"

                package = {
                    "brand": ch["slug"],
                    "display_name": ch["display_name"],
                    "handle": ch["handle"],
                    "title": ch["title"],
                    "description": ch["description"],
                    "script": ch["script"],
                    "narration_voice": ch["voice"],
                    "video_path": str(final_mp4),
                    "status": "published",
                    "published_at": datetime.now().isoformat(),
                    "play_url": play_url
                }

                with open(json_path, 'w', encoding='utf-8') as f:
                    json.dump(package, f, indent=2)

                print(f"  - SUCCESS: {ch['display_name']} Movie Recap ({size_mb} MB) -> {ch['slug']}.mp4")
                print(f"  - Playable Link: {play_url}")

        for tmp in [raw_yt, voice_mp3, voice_vtt]:
            if tmp.exists():
                try:
                    tmp.unlink()
                except Exception:
                    pass


if __name__ == "__main__":
    run_cinematic_movie_recap_pipeline()
