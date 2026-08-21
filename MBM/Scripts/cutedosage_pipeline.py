import os
import sys
import json
import requests
import subprocess
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(BASE_DIR, '..', 'clipping-factory', 'MBM-Social', 'Brands', 'cutedosage', 'outputs')
os.makedirs(OUTPUT_DIR, exist_ok=True)

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "").strip()

US_VIRAL_KEYWORDS = [
    "cute puppy doing funny things",
    "golden retriever baby reaction",
    "funny cat talking back",
    "cute baby laughing with dog",
    "wholesome animal bond america"
]

def search_us_viral_clips(query):
    url = "https://youtube138.p.rapidapi.com/search/"
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "youtube138.p.rapidapi.com"
    }
    params = {"q": query, "hl": "en", "gl": "US"}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=15)
        if res.status_code == 200:
            data = res.json()
            contents = data.get('contents', [])
            results = []
            for item in contents:
                video = item.get('video', {})
                if video and video.get('lengthSeconds', 999) <= 60: # Shorts length
                    results.append({
                        "id": video.get('videoId'),
                        "title": video.get('title'),
                        "views": video.get('stats', {}).get('views', 0),
                        "url": f"https://www.youtube.com/watch?v={video.get('videoId')}"
                    })
            return results
    except Exception as e:
        print(f"[CUTE DOSAGE] Search error: {e}")
    return []

def generate_higgsfield_thumbnail_prompt(concept):
    cmd = [
        "higgsfield", "generate", "create", "z_image",
        "--prompt", f"Super cute adorable pastel style thumbnail cover for YouTube Shorts about {concept}, vibrant lighting, 8k resolution, Disney Pixar animation style",
        "--wait"
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=120, shell=True)
        if res.returncode == 0:
            output = res.stdout.strip()
            print(f"[HIGGSFIELD THUMBNAIL] Asset generated: {output}")
            return output
    except Exception as e:
        print(f"[HIGGSFIELD THUMBNAIL] Error: {e}")
    return None

def run_cutedosage_pipeline():
    print("=== Launching Cute Dosage US Content Pipeline ===")
    all_targets = []
    for kw in US_VIRAL_KEYWORDS:
        print(f"[CUTE DOSAGE] Scanning viral US Shorts for: {kw}")
        clips = search_us_viral_clips(kw)
        if clips:
            all_targets.extend(clips[:3])

    print(f"[CUTE DOSAGE] Found {len(all_targets)} high-potential US viral clips!")
    
    pipeline_file = os.path.join(OUTPUT_DIR, f"cutedosage_campaign_{datetime.now().strftime('%Y%m%d')}.json")
    with open(pipeline_file, 'w', encoding='utf-8') as f:
        json.dump({
            "brand": "cutedosage",
            "target_audience": "US / Worldwide",
            "campaign_date": datetime.now().isoformat(),
            "scheduled_posting": "14:00-22:00 UTC (US Peak Hours)",
            "clips": all_targets
        }, f, indent=2)

    print(f"[SUCCESS] Cute Dosage pipeline campaign generated: {pipeline_file}")

if __name__ == "__main__":
    run_cutedosage_pipeline()
