import json
import os
import sys
import shutil
import time
from pathlib import Path

from .high_reach_virality_agent import HighReachViralityAgent
from .clipping_quality_agent import ClippingQualityAgent
from .adaptive_velocity_agent import AdaptiveVelocityAgent
from .social_trend_jack_agent import SocialTrendJackAgent
from . import anty_shadowban_agent

ROOT = Path(__file__).resolve().parent.parent
PUBLISH_QUEUE = ROOT / "publish_queue"
REJECTED_DIR = PUBLISH_QUEUE / "rejected_quality"
STALE_DIR = PUBLISH_QUEUE / "stale_pre_enhancement"

def run_multi_agent_pipeline():
    REJECTED_DIR.mkdir(exist_ok=True, parents=True)
    STALE_DIR.mkdir(exist_ok=True, parents=True)
    
    print("[*] Initializing Pipeline...")
    
    # 1. Initialize Trend Agent
    trend_agent = SocialTrendJackAgent()
    trends = trend_agent.scan_for_trends()
    top_trend = None
    if trends:
        top_trend = sorted(trends, key=lambda x: x["volume"], reverse=True)[0]
        print(f"[*] Top trend identified: #{top_trend['topic']}")
        
    count_processed = 0
    count_rejected = 0
    count_enhanced = 0
    
    files = list(PUBLISH_QUEUE.glob("*.json"))
    
    for file in files:
        if not file.is_file():
            continue
            
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            continue
            
        # Determine brand and niche
        brand = data.get("brand_slug")
        if not brand:
            name_parts = file.stem.split("_")
            for b in ["cutedosage", "dontwatchthis", "goalmachinez", "twistsrevealed", "clippingfactorymbm"]:
                if b in name_parts:
                    brand = b
                    break
        if not brand:
            print(f"Skipping {file.name} - could not determine brand.")
            continue
            
        niche = data.get("niche", "tech")
        base_title = data.get("viral_title") or data.get("title") or "Amazing Video"
        if "|" in base_title:
            base_title = base_title.split("|")[0].strip()
            
        # --- AGENT 1: Quality Audit ---
        quality_agent = ClippingQualityAgent(brand)
        audit_result = quality_agent.audit_clip_quality(data)
        if not audit_result.get("approved", True):
            print(f"[REJECTED] {file.name} failed quality audit (Score: {audit_result.get('quality_score')})")
            shutil.move(str(file), str(REJECTED_DIR / file.name))
            count_rejected += 1
            continue
            
        # --- AGENT 2: Virality Agent ---
        viral_agent = HighReachViralityAgent(brand)
        v2_opt = viral_agent.optimize_package_for_maximum_reach(base_title, niche)
        
        # --- AGENT 3: Trend Jacking ---
        if top_trend:
            v2_opt["description"] = f"Riding the #{top_trend['topic']} wave! {v2_opt.get('description', '')}"
            if "hashtags" in v2_opt:
                v2_opt["hashtags"].append(top_trend['topic'])
                
        # Merge new V2 perks into the payload
        new_payload = {**data, **v2_opt}
        new_payload["v2_upgrade_timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        new_payload["quality_score"] = audit_result.get("quality_score", 100)
        
        # Save new file
        new_filename = f"multi_agent_v3_{brand}_{int(time.time())}_{count_enhanced}.json"
        new_filepath = PUBLISH_QUEUE / new_filename
        
        with open(new_filepath, "w", encoding="utf-8") as f:
            json.dump(new_payload, f, indent=2)
            
        # Move old file to stale
        shutil.move(str(file), str(STALE_DIR / file.name))
        count_enhanced += 1
        count_processed += 1
        
    print(f"\n[*] Phase 1 Complete. Processed {count_processed}. Enhanced {count_enhanced}. Rejected {count_rejected}.")
    
    # --- PHYSICAL VIDEO ENHANCEMENT ---
    print("\n[*] Initializing Physical AI Video Quality Enhancer...")
    try:
        sys.path.append(str(ROOT))
        import video_quality_auditor_enhancer
        video_quality_auditor_enhancer.run_quality_audit_and_enhancement()
    except Exception as e:
        print(f"[-] Video physical enhancement skipped: {e}")
    
    # --- AGENT 4 & 5: Velocity & Shadowban ---
    print("\n[*] Initializing Anty-Shadowban Agent for smart scheduling...")
    # anty_shadowban_agent generates schedules for all files in the queue
    schedule_result = anty_shadowban_agent.run(schedule_days=7, dry_run=False)
    print(f"[*] Shadowban scheduling complete. Packages scheduled.")
    
if __name__ == "__main__":
    run_multi_agent_pipeline()
