import os, subprocess, json
from pathlib import Path

try:
    from seedance_video_engine import Seedance25VideoEngine
except ImportError:
    from mbm_social.seedance_video_engine import Seedance25VideoEngine

DEFAULT_VIDEO_MODEL = "seedance-2.5-ultra"

def apply_motion_background(input_video: str, output_video: str, background_style: str = "abstract_motion"):
    """
    Overlays or composites vertical video over high-quality moving background motion loop.
    Ensures 1080x1920 60FPS vertical output with unsharp contrast and proper safety margins.
    """
    in_path = Path(input_video)
    out_path = Path(output_video)
    
    if not in_path.exists():
        print(f"[MOTION ENGINE] Input video not found: {input_video}")
        return False
        
    print(f"[MOTION ENGINE] Applying 1080x1920 60FPS High-Bitrate Motion Background ({background_style})...")
    
    # FFmpeg filter: Blur-background + Sharp foreground stack + 1080x1920 60FPS HD output
    complex_filter = (
        "[0:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=20:steps=2,eq=brightness=-0.1:contrast=1.1[bg];"
        "[0:v]scale=1000:-1,unsharp=5:5:1.0:5:5:0.0[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2[v]"
    )
    
    cmd = [
        "ffmpeg", "-y",
        "-i", str(in_path),
        "-filter_complex", complex_filter,
        "-map", "[v]",
        "-map", "0:a?",
        "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-r", "60",
        "-c:a", "aac", "-b:a", "320k",
        str(out_path)
    ]
    
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            print(f"[MOTION ENGINE] SUCCESS: Output saved to {out_path.name}")
            return True
        else:
            print(f"[MOTION ENGINE] FFmpeg error: {res.stderr[:300]}")
            return False
    except Exception as e:
        print(f"[MOTION ENGINE] Execution exception: {e}")
        return False
