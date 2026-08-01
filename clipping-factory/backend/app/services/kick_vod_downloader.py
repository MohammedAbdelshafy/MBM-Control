"""
Kick VOD Stream Downloader Bypassing Live Stream Block
Uses Streamlink / ScrapeNinja HLS playlist extraction.
"""
import subprocess
import sys
import os

def download_kick_vod(video_url: str, output_path: str) -> bool:
    print(f"[KICK VOD] Downloading VOD: {video_url} -> {output_path}")
    # Streamlink HLS extraction
    cmd = [
        "streamlink",
        "--stream-segment-threads", "4",
        video_url, "best",
        "-o", output_path
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 10000:
            print("[KICK VOD] Download successful via Streamlink HLS!")
            return True
    except Exception as e:
        print(f"[KICK VOD] Streamlink notice: {e}")
        
    # Fallback yt-dlp with HLS options
    cmd_ytdlp = [
        sys.executable, "-m", "yt_dlp",
        "--concurrent-fragments", "5",
        "--hls-use-mpegts",
        "-o", output_path,
        video_url
    ]
    try:
        subprocess.run(cmd_ytdlp, capture_output=True, text=True, timeout=120)
        return os.path.exists(output_path) and os.path.getsize(output_path) > 10000
    except Exception as e:
        print(f"[KICK VOD] yt-dlp notice: {e}")
        return False

if __name__ == "__main__":
    test_url = sys.argv[1] if len(sys.argv) > 1 else "https://kick.com/video/test"
    download_kick_vod(test_url, "kick_test.mp4")
