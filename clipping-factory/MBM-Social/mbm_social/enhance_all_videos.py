import json
import os
import shutil
import time
from pathlib import Path

from high_reach_virality_agent import HighReachViralityAgent

ROOT = Path(__file__).resolve().parent.parent
PUBLISH_QUEUE = ROOT / "publish_queue"
STALE_DIR = PUBLISH_QUEUE / "stale_pre_enhancement"

def upgrade_videos():
    STALE_DIR.mkdir(exist_ok=True, parents=True)
    
    count = 0
    for file in PUBLISH_QUEUE.glob("*.json"):
        if not file.is_file():
            continue
            
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
            
        # Check if it already has v2.0
        if data.get("agent_name") == "HighReachViralityAgent v2.0":
            continue
            
        # Determine brand and niche
        # Some files are named pkg_15min_<brand>_<timestamp>.json or enhanced_<brand>_viral.json
        brand = data.get("brand_slug")
        if not brand:
            # try to extract from filename
            name_parts = file.stem.split("_")
            for b in ["cutedosage", "dontwatchthis", "goalmachinez", "twistsrevealed", "clippingfactorymbm"]:
                if b in name_parts:
                    brand = b
                    break
                    
        if not brand:
            print(f"Skipping {file.name} - could not determine brand.")
            continue
            
        niche = data.get("niche", "tech") # default to tech if missing
        base_title = data.get("viral_title") or data.get("title") or "Amazing Video"
        
        # Clean title from old hashtags
        if "|" in base_title:
            base_title = base_title.split("|")[0].strip()
            
        print(f"Upgrading {file.name} to V2.0...")
        
        # Instantiate V2 agent
        agent = HighReachViralityAgent(brand)
        v2_opt = agent.optimize_package_for_maximum_reach(base_title, niche)
        
        # Merge new V2 perks into the payload
        new_payload = {**data, **v2_opt}
        new_payload["v2_upgrade_timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        
        # Save new file
        new_filename = f"enhanced_v2_{brand}_{int(time.time())}_{count}.json"
        new_filepath = PUBLISH_QUEUE / new_filename
        
        with open(new_filepath, "w", encoding="utf-8") as f:
            json.dump(new_payload, f, indent=2)
            
        # Move old file to stale
        shutil.move(str(file), str(STALE_DIR / file.name))
        count += 1
        
    print(f"\n[Upgrade Complete] Successfully upgraded {count} packages to Virality V2.0!")

if __name__ == "__main__":
    upgrade_videos()
