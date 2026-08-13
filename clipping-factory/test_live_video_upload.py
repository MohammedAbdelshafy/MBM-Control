"""
Live YouTube Video Upload Test & Verification Engine
=====================================================
Tests and executes immediate live uploads of harvested HD source video clips
to YouTube Shorts using YouTube Data API v3 and CDP Browser Publisher.

Run:
  python clipping-factory/test_live_video_upload.py
"""

import os
import sys
import io
import json
import time
from pathlib import Path
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BASE_DIR.parent
MBM_SOCIAL_DIR = BASE_DIR / "MBM-Social"
sys.path.insert(0, str(MBM_SOCIAL_DIR))

import mbm_social.youtube_api_publisher as yt_api
import mbm_social.youtube_cdp_publisher as cdp_pub
import mbm_social.publisher as pw_pub

TOKENS_PATH = MBM_SOCIAL_DIR / "youtube_tokens.json"
DEMOS_DIR = MBM_SOCIAL_DIR / "public" / "demos"


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[LIVE UPLOAD ENGINE 🎬] [{ts}] {msg}"
    print(line)


def run_live_upload_test():
    log("==========================================================")
    log("  EXECUTING LIVE YOUTUBE SHORTS UPLOAD & VERIFICATION     ")
    log("==========================================================")

    # 1. Target harvest clip
    action_clip = DEMOS_DIR / "real_action_thriller_source.mp4"
    if not action_clip.exists():
        action_clip = DEMOS_DIR / "demo_ai-clipping.mp4"

    title = "Top 3 Action Movie Ending Twists That Shocked American Cinema #Shorts #USA"
    desc = "Insane action & thriller plot twists that had American moviegoers speechless!\n\n" \
           "💰 Get Instant Access: https://member.neteller.com/pay?email=abdelshafyclapps@gmail.com&account=4599228811&amount=997.00&currency=USD\n" \
           "🌐 Live Portal: https://mbm-dialer.higgsfield.app\n\n" \
           "#MovieRecap #Action #Thriller #HollywoodRecap #USA #USATrending"

    log(f"📹 Source Clip: {action_clip.name} ({action_clip.stat().st_size / (1024*1024):.2f} MB)")
    log(f"📌 Title: {title}")

    # Attempt Path 1: YouTube Data API v3
    log("\n[PATH 1] Attempting YouTube Data API v3 Upload...")
    success, video_id = yt_api.publish_via_api(str(action_clip), title, desc, channel_id="clippingfactorymbm")

    if success and video_id:
        log(f"🎉 SUCCESS! Live Video Published via API -> https://youtube.com/shorts/{video_id}")
        return True

    log("ℹ️ Direct API upload pending OAuth refresh. Attempting Path 2 (CDP / Playwright Browser Upload)...")

    # Attempt Path 2: Native CDP Browser Upload (port 9222)
    success_cdp, vid_cdp, url_cdp = cdp_pub.publish_via_cdp(str(action_clip), title, desc)
    if success_cdp:
        log(f"🎉 SUCCESS! Live Video Uploaded via Native CDP Browser -> {url_cdp}")
        return True

    # Attempt Path 3: Playwright Persistent Session Upload
    log("ℹ️ Attempting Path 3 (Playwright Studio Session Upload)...")
    pw_res = pw_pub.upload_to_youtube(str(action_clip), title, desc, brand="clippingfactorymbm")
    if pw_res:
        log(f"🎉 SUCCESS! Live Video Uploaded via Playwright Studio!")
        return True

    log("==========================================================")
    log("⚠️ All live upload channels tested. System awaiting active refresh token or CDP port 9222 connection.")
    log("==========================================================")
    return False


if __name__ == "__main__":
    run_live_upload_test()
