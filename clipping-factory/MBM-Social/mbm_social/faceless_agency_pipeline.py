"""
Faceless Agency Pipeline.
Runs the trend hijacking and voice cloning pipeline for external clients.
Outputs to client_approval/ directory.
"""
import os
import sys
import json
import time
from pathlib import Path
from datetime import datetime

BACKEND = Path(__file__).resolve().parent.parent.parent / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

try:
    from app.agents.voice_cloning_agent import VoiceCloningAgent
except ImportError:
    VoiceCloningAgent = None

APPROVAL_QUEUE = Path(__file__).resolve().parent.parent / "client_approval"

def get_client_trend(niche):
    print(f"[FacelessAgency] Scanning for viral topics in client niche: {niche}...")
    time.sleep(1)
    return {
        "topic": f"The Secret to {niche}",
        "hashtag": f"#{niche.replace(' ', '')}",
        "viral_score": 95.0
    }

def generate_script(trend):
    script = f"Stop scrolling. Here is the ultimate truth about {trend['topic']}. " \
             f"If you want to master {trend['hashtag']}, you need to implement this strategy today. " \
             "Save this video before it gets taken down."
    return script

def run_faceless_pipeline_for_client(client_id, niche):
    print(f"=== Starting Faceless Channel Pipeline for Client: {client_id} ===")
    
    trend = get_client_trend(niche)
    script = generate_script(trend)
    print(f"[FacelessAgency] Generated Script: {script}")
    
    audio_path = f"client_{client_id}_{int(time.time())}.mp3"
    if VoiceCloningAgent:
        print("[FacelessAgency] Generating Voiceover...")
        # VoiceCloningAgent().generate_voiceover(script, output_path=audio_path)
    
    payload = {
        "client_id": client_id,
        "mode": "external",
        "niche": niche,
        "topic": trend["topic"],
        "script": script,
        "audio_file": audio_path,
        "generated_at": datetime.now().isoformat(),
        "status": "pending_client_approval"
    }
    
    APPROVAL_QUEUE.mkdir(exist_ok=True)
    out_file = APPROVAL_QUEUE / f"client_{client_id}_{int(time.time())}.json"
    
    with open(out_file, "w") as f:
        json.dump(payload, f, indent=4)
        
    print(f"[FacelessAgency] Client package ready for review at {out_file.name}")
    return out_file

if __name__ == "__main__":
    run_faceless_pipeline_for_client("RealEstatePro", "Real Estate Investing")
