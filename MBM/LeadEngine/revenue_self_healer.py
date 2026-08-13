import json
import os
import sys

# Paths to important config and state files
REVENUE_VERDICT_PATH = "/tmp/revenue_verdict.json"
PERSISTENCE_FILE = "MBM/LeadEngine/agent_persistence.json"

def heal():
    print("Initializing Revenue Self-Healing Protocol...")
    
    if not os.path.exists(REVENUE_VERDICT_PATH):
        print("No revenue verdict found. Skipping self-heal.")
        return
        
    try:
        with open(REVENUE_VERDICT_PATH, "r") as f:
            verdict = json.load(f)
    except Exception as e:
        print(f"Failed to load revenue verdict: {e}")
        return

    score = verdict.get("score", 0)
    level = verdict.get("escalation_level", "NORMAL")
    hours = verdict.get("cumulative_hours_without_revenue", 0)
    
    if score >= 40 and hours < 12 and level == "NORMAL":
        print("Revenue looks stable. No healing required.")
        return
        
    print(f"CRITICAL: Revenue stalled (Score: {score}, Hours: {hours}). Attempting pivot...")
    
    if not os.path.exists(PERSISTENCE_FILE):
        print(f"{PERSISTENCE_FILE} not found. Cannot pivot niches.")
        return
        
    try:
        with open(PERSISTENCE_FILE, "r") as f:
            persistence = json.load(f)
    except Exception as e:
        print(f"Failed to load persistence data: {e}")
        return
        
    # Rotate the active niche.
    # Assumes niches are numbered 0 to 3 as seen in agent_factory.py
    current_niche = persistence.get("active_niche_index", 0)
    next_niche = (current_niche + 1) % 4
    
    persistence["active_niche_index"] = next_niche
    persistence["healing_events"] = persistence.get("healing_events", 0) + 1
    
    # Save the rotated state
    try:
        with open(PERSISTENCE_FILE, "w") as f:
            json.dump(persistence, f, indent=2)
        print(f"Successfully pivoted from Niche {current_niche} to Niche {next_niche}.")
    except Exception as e:
        print(f"Failed to save persistence data: {e}")
        
    print("Self-Healing Protocol complete. The next Agent Factory run will use the new niche.")

if __name__ == "__main__":
    heal()
