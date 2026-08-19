"""Step 3-4: Direct YouTube upload via API for first real publication."""
import sys
import json
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mbm_social.youtube_api_publisher import publish_via_api, tokens_exist_for

brand = "clippingfactorymbm"
video_path = Path("publish_queue/first_real_publish.mp4")
title = "MBM Social - First Real Test Upload [UNLISTED]"
description = "Controlled test publication for MBM-Social production validation. This is an unlisted test video."

if not video_path.exists():
    print("ERROR: Video file not found")
    sys.exit(1)

if not tokens_exist_for(brand):
    print("ERROR: No valid tokens for brand")
    sys.exit(1)

print(f"brand: {brand}")
print(f"video: {video_path}")
print(f"title: {title}")
print(f"privacy: unlisted")
print()
print("Uploading...")

ok, video_id = publish_via_api(
    str(video_path),
    title,
    description,
    brand=brand,
    privacy_status="unlisted",
)

if ok and video_id:
    url = f"https://www.youtube.com/watch?v={video_id}"
    print()
    print("UPLOAD: SUCCESS")
    print(f"video_id: {video_id}")
    print(f"url: {url}")

    # Save evidence
    evidence_dir = Path("artifacts/production_qa/first_publish")
    evidence_dir.mkdir(parents=True, exist_ok=True)
    evidence = {
        "platform": "youtube",
        "brand": brand,
        "mode": "test",
        "privacy": "unlisted",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "video_id": video_id,
        "url": url,
        "title": title,
        "creative_score": 7.5,
        "creative_tier": "PUBLISH",
        "source_video": str(video_path),
    }
    (evidence_dir / "publish_evidence.json").write_text(
        json.dumps(evidence, indent=2), encoding="utf-8"
    )
    print(f"Evidence saved: {evidence_dir / 'publish_evidence.json'}")
else:
    print()
    print("UPLOAD: FAILED")
    print("No real video ID returned")
    sys.exit(1)
