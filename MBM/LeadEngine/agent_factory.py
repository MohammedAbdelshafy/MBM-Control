#!/usr/bin/env python3
"""
MBM Voice Agent Factory
Generates and deploys NEW voice agents every 15 minutes to Retell AI.
Each agent targets a different niche/industry for maximum coverage.

Usage:
  python agent_factory.py --once        # Generate 1 agent now
  python agent_factory.py --loop        # Generate every 15 min (runs forever)
  python agent_factory.py --deploy      # Deploy all agents to Retell
  python agent_factory.py --status      # Show all deployed agents
"""

import json
import os
import sys
import time
import random
import hashlib
import argparse
from pathlib import Path
from datetime import datetime

try:
    import requests
except ImportError:
    os.system(f"{sys.executable} -m pip install requests -q")
    import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT / "MBM" / "LeadEngine" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
AGENTS_FILE = LOGS_DIR / "factory_agents.json"
DEPLOYED_FILE = LOGS_DIR / "deployed_agents.json"

RETELL_API_KEY = os.getenv("RETELL_API_KEY")

# Voice IDs for variety (Retell native voices — only verified working IDs)
VOICE_IDS = [
    "retell-Willa",
    "retell-Cimo",
]

# Industry niches with scripts
NICHES = [
    {
        "name": "HVAC Repair",
        "persona": "Friendly HVAC service coordinator",
        "hook": "Hi! I'm calling about your heating and cooling system. Are you still experiencing issues with your HVAC?",
        "qualify": ["What's the issue?", "When did it start?", "What's your address?", "Is this residential or commercial?"],
        "close": "I'll have a technician call you within 30 minutes. What's the best number?",
        "rate": 0.35,
        "tags": ["hvac", "home-services", "repair"]
    },
    {
        "name": "Plumbing Emergency",
        "persona": "Calm, professional plumbing dispatcher",
        "hook": "Hi! I see you submitted a plumbing request. Is this still an emergency, or has the situation changed?",
        "qualify": ["What's the issue?", "Is water still running?", "What's your address?", "What's your timeline?"],
        "close": "A licensed plumber will call you within 15 minutes. Hang tight!",
        "rate": 0.35,
        "tags": ["plumbing", "emergency", "home-services"]
    },
    {
        "name": "Solar Panel Sales",
        "persona": "Energetic clean energy consultant",
        "hook": "Hi! I'm calling about solar panels for your home. Are you still interested in reducing your electricity bill by 30-50%?",
        "qualify": ["What's your monthly electric bill?", "Do you own your home?", "What's your roof direction?", "When are you looking to install?"],
        "close": "I'll send you a free solar estimate. What email works best?",
        "rate": 0.45,
        "tags": ["solar", "energy", "home-improvement"]
    },
    {
        "name": "Roofing Contractor",
        "persona": "Professional roofing consultant",
        "hook": "Hi! I'm following up on your roofing inquiry. Are you still looking to get your roof inspected or repaired?",
        "qualify": ["What's the issue?", "When was the last inspection?", "What type of roof?", "Is there visible damage?"],
        "close": "We can schedule a free inspection this week. What day works best?",
        "rate": 0.40,
        "tags": ["roofing", "contractor", "home-services"]
    },
    {
        "name": "Insurance Claims",
        "persona": "Empathetic insurance claim specialist",
        "hook": "Hi! I'm following up on your insurance claim. Are you still need assistance with the claims process?",
        "qualify": ["What type of claim?", "When did the incident occur?", "Have you filed yet?", "What's your policy number?"],
        "close": "I'll have an adjuster review your case within 24 hours. We'll call you back.",
        "rate": 0.50,
        "tags": ["insurance", "claims", "financial"]
    },
    {
        "name": "Legal Consultation",
        "persona": "Professional legal intake specialist",
        "hook": "Hi! I'm calling from the law office. You requested a consultation. Are you still looking for legal assistance?",
        "qualify": ["What type of case?", "When did this happen?", "Have you spoken to an attorney?", "What's your timeline?"],
        "close": "An attorney will call you within 2 hours for a free consultation.",
        "rate": 0.55,
        "tags": ["legal", "consultation", "professional"]
    },
    {
        "name": "Dental Appointment",
        "persona": "Warm dental office receptionist",
        "hook": "Hi! I'm calling about your upcoming dental appointment. Are you still able to make it?",
        "qualify": ["What procedure?", "Do you have insurance?", "Any preferences for date/time?", "Any anxiety concerns?"],
        "close": "I'll confirm your appointment and send a reminder. See you soon!",
        "rate": 0.30,
        "tags": ["dental", "healthcare", "appointment"]
    },
    {
        "name": "Auto Detailing",
        "persona": "Enthusiastic auto detailing coordinator",
        "hook": "Hi! I'm following up on your auto detailing request. Are you still looking to get your vehicle detailed?",
        "qualify": ["What type of vehicle?", "Interior, exterior, or both?", "Any special requests?", "When works for you?"],
        "close": "I'll book your detail slot. What day works best?",
        "rate": 0.35,
        "tags": ["auto", "detailing", "services"]
    },
    {
        "name": "Moving Company",
        "persona": "Organized moving coordinator",
        "hook": "Hi! I'm calling about your upcoming move. Are you still planning to relocate?",
        "qualify": ["When are you moving?", "What's the origin/destination?", "How many rooms?", "Any specialty items?"],
        "close": "I'll prepare a custom quote. When can we do a virtual walkthrough?",
        "rate": 0.40,
        "tags": ["moving", "logistics", "services"]
    },
    {
        "name": "Pest Control",
        "persona": "Knowledgeable pest control specialist",
        "hook": "Hi! I'm following up on your pest control request. Are you still experiencing pest issues?",
        "qualify": ["What type of pests?", "How long have you noticed them?", "What's your home size?", "Any pets or children?"],
        "close": "We can treat your home this week. What day works best?",
        "rate": 0.35,
        "tags": ["pest-control", "home-services", "maintenance"]
    },
    {
        "name": "Landscaping",
        "persona": "Creative landscaping consultant",
        "hook": "Hi! I'm calling about your landscaping project. Are you still looking to improve your outdoor space?",
        "qualify": ["What services needed?", "What's your budget?", "What's your yard size?", "Any specific ideas?"],
        "close": "I'll design a custom proposal. Can we schedule a site visit this week?",
        "rate": 0.40,
        "tags": ["landscaping", "outdoor", "home-improvement"]
    },
    {
        "name": "Pool Service",
        "persona": "Friendly pool maintenance coordinator",
        "hook": "Hi! I'm following up on your pool service request. Is your pool still needing maintenance or repair?",
        "qualify": ["What's the issue?", "Pool size?", "How often do you use it?", "Last time it was serviced?"],
        "close": "A pool tech will call you within 1 hour. What's the best number?",
        "rate": 0.35,
        "tags": ["pool", "maintenance", "home-services"]
    },
    {
        "name": "Window Cleaning",
        "persona": "Efficient window cleaning dispatcher",
        "hook": "Hi! I'm calling about your window cleaning request. Are you still looking to get your windows cleaned?",
        "qualify": ["How many windows?", "Interior, exterior, or both?", "Any high or hard-to-reach?", "When works for you?"],
        "close": "I'll book your cleaning slot. What day works best?",
        "rate": 0.30,
        "tags": ["cleaning", "window", "services"]
    },
    {
        "name": "Painting Contractor",
        "persona": "Detail-oriented painting consultant",
        "hook": "Hi! I'm following up on your painting project. Are you still looking to get your space painted?",
        "qualify": ["Interior or exterior?", "What areas need painting?", "What colors?", "Any prep needed?"],
        "close": "I'll prepare a free estimate. Can we do a walkthrough this week?",
        "rate": 0.40,
        "tags": ["painting", "contractor", "home-improvement"]
    },
    {
        "name": "Electrical Services",
        "persona": "Licensed electrical coordinator",
        "hook": "Hi! I'm calling about your electrical issue. Are you still experiencing problems?",
        "qualify": ["What's the issue?", "Is it urgent?", "What's your address?", "Any safety concerns?"],
        "close": "A licensed electrician will call you within 30 minutes.",
        "rate": 0.45,
        "tags": ["electrical", "home-services", "emergency"]
    },
    {
        "name": "Concrete & Foundation",
        "persona": "Structural foundation specialist",
        "hook": "Hi! I'm following up on your foundation inquiry. Are you noticing any cracks or settling?",
        "qualify": ["What issues do you see?", "When did you first notice?", "What type of foundation?", "How old is the property?"],
        "close": "We'll schedule a free inspection this week. What day works best?",
        "rate": 0.50,
        "tags": ["concrete", "foundation", "contractor"]
    },
    {
        "name": "Fence Installation",
        "persona": "Friendly fencing coordinator",
        "hook": "Hi! I'm calling about your fence project. Are you still looking to install or repair a fence?",
        "qualify": ["What type of fence?", "Linear footage needed?", "Any HOA restrictions?", "What's your timeline?"],
        "close": "I'll prepare a custom quote. Can we measure your yard this week?",
        "rate": 0.35,
        "tags": ["fencing", "contractor", "home-improvement"]
    },
    {
        "name": "Garage Door",
        "persona": "Quick garage door specialist",
        "hook": "Hi! I'm calling about your garage door issue. Is it still not working properly?",
        "qualify": ["What's the issue?", "Manual or automatic?", "When did it stop working?", "What brand?"],
        "close": "A tech will call you within 20 minutes. We offer same-day repair.",
        "rate": 0.35,
        "tags": ["garage-door", "repair", "home-services"]
    },
    {
        "name": "Gutter Cleaning",
        "persona": "Efficient gutter service coordinator",
        "hook": "Hi! I'm following up on your gutter cleaning request. Are you still looking to get your gutters cleaned?",
        "qualify": ["How many linear feet?", "Any visible damage?", "When was the last cleaning?", "Are you noticing overflow?"],
        "close": "I'll book your gutter cleaning this week. What day works?",
        "rate": 0.30,
        "tags": ["gutter", "cleaning", "home-services"]
    },
    {
        "name": "Handyman Services",
        "persona": "Versatile handyman coordinator",
        "hook": "Hi! I'm calling about your handyman request. What repairs or projects do you need help with?",
        "qualify": ["What's the project?", "How urgent?", "What's your budget?", "Any specific skills needed?"],
        "close": "I'll match you with the right handyman. What day works for the job?",
        "rate": 0.35,
        "tags": ["handyman", "repairs", "general"]
    },
    {
        "name": "Carpet Cleaning",
        "persona": "Professional carpet cleaning dispatcher",
        "hook": "Hi! I'm following up on your carpet cleaning request. Are you still looking to get your carpets cleaned?",
        "qualify": ["How many rooms?", "Any stains or pet damage?", "What type of carpet?", "When works for you?"],
        "close": "I'll book your carpet cleaning. What day works best?",
        "rate": 0.30,
        "tags": ["carpet", "cleaning", "home-services"]
    },
    {
        "name": "Appliance Repair",
        "persona": "Knowledgeable appliance repair coordinator",
        "hook": "Hi! I'm calling about your appliance issue. Is it still malfunctioning?",
        "qualify": ["What appliance?", "What's the issue?", "Brand and model?", "Still under warranty?"],
        "close": "A tech will call you within 1 hour. Same-day repair available.",
        "rate": 0.40,
        "tags": ["appliance", "repair", "home-services"]
    },
    {
        "name": "Home Inspection",
        "persona": "Thorough home inspection coordinator",
        "hook": "Hi! I'm calling about your home inspection. Are you still looking to schedule one?",
        "qualify": ["Buying or selling?", "What's the address?", "When's the deadline?", "Any known issues?"],
        "close": "I'll book your inspection. What day works for the walkthrough?",
        "rate": 0.45,
        "tags": ["inspection", "real-estate", "professional"]
    },
    {
        "name": "Tree Service",
        "persona": "Experienced tree care specialist",
        "hook": "Hi! I'm following up on your tree service request. Do you still need tree work done?",
        "qualify": ["What service needed?", "How many trees?", "Any emergency?", "Access to the area?"],
        "close": "We can have a crew out this week. What day works?",
        "rate": 0.40,
        "tags": ["tree", "landscaping", "home-services"]
    },
    {
        "name": "Pressure Washing",
        "persona": "Energetic pressure washing coordinator",
    "hook": "Hi! I'm calling about pressure washing your property. Are you still looking to get it cleaned?",
        "qualify": ["What areas?", "How many sq ft?", "Any delicate surfaces?", "When works for you?"],
        "close": "I'll book your pressure wash this week. What day works?",
        "rate": 0.30,
        "tags": ["pressure-washing", "cleaning", "exterior"]
    },
    {
        "name": "Flooring Installation",
        "persona": "Professional flooring consultant",
        "hook": "Hi! I'm following up on your flooring project. Are you still looking to install new flooring?",
        "qualify": ["What type of flooring?", "Which rooms?", "What's your budget?", "When do you want it done?"],
        "close": "I'll prepare a custom estimate. Can we measure your space this week?",
        "rate": 0.45,
        "tags": ["flooring", "installation", "home-improvement"]
    },
    {
        "name": "Smart Home Setup",
        "persona": "Tech-savvy smart home specialist",
        "hook": "Hi! I'm calling about setting up your smart home. Are you still interested in automation?",
        "qualify": ["What devices?", "What's your budget?", "What platform (Alexa/Google)?", "Any specific goals?"],
        "close": "I'll design a custom setup. Can we do a virtual consult this week?",
        "rate": 0.50,
        "tags": ["smart-home", "technology", "installation"]
    },
    {
        "name": "Water Heater",
        "persona": "Quick water heater specialist",
        "hook": "Hi! I'm calling about your water heater. Is it still not working properly?",
        "qualify": ["Gas or electric?", "What's the issue?", "How old is it?", "Tank or tankless?"],
        "close": "We can install a new unit tomorrow. What time works?",
        "rate": 0.40,
        "tags": ["water-heater", "plumbing", "repair"]
    },
    {
        "name": "Attic Insulation",
        "persona": "Energy efficiency specialist",
        "hook": "Hi! I'm following up on your insulation inquiry. Are you still looking to improve your home's energy efficiency?",
        "qualify": ["What's your current insulation?", "What's your energy bill?", "What's your home size?", "Any cold spots?"],
        "close": "We can insulate your attic this week. What day works?",
        "rate": 0.40,
        "tags": ["insulation", "energy", "home-improvement"]
    },
]


def load_deployed():
    if DEPLOYED_FILE.exists():
        with open(DEPLOYED_FILE, "r") as f:
            return json.load(f)
    return []


def save_deployed(deployed):
    with open(DEPLOYED_FILE, "w") as f:
        json.dump(deployed, f, indent=2)


def get_next_niche():
    """Pick a niche that hasn't been deployed yet, or cycle back"""
    deployed = load_deployed()
    deployed_names = {d["niche"] for d in deployed}

    available = [n for n in NICHES if n["name"] not in deployed_names]
    if not available:
        # All deployed, pick random one
        available = NICHES

    return random.choice(available)


def create_agent(niche):
    """Create a new voice agent for a niche and deploy to Retell"""
    if not RETELL_API_KEY:
        print("[!] RETELL_API_KEY not set")
        return None

    headers = {"Authorization": f"Bearer {RETELL_API_KEY}", "Content-Type": "application/json"}

    prompt = f"""You are {niche['persona']}. 

Opening: "{niche['hook']}"

Qualification questions:
{chr(10).join('- ' + q for q in niche['qualify'])}

Closing: "{niche['close']}"

If they say NO: "No problem. If you need {niche['name'].lower()} services in the future, we're here to help. Have a great day!"
If they say NOT NOW: "Totally understand. Should I check back in a week or two?"
If they say ALREADY DONE: "Great! If you need anything else, don't hesitate to reach out."
If they're BUSY: "I understand. When would be a better time for a quick 2-minute call?"

Be natural, empathetic, and professional. Never be pushy. Log the outcome."""

    voice_id = random.choice(VOICE_IDS)

    # Step 1: Create LLM first
    llm_payload = {
        "model": "gemini-2.0-flash",
        "general_prompt": prompt
    }

    try:
        r = requests.post("https://api.retellai.com/create-retell-llm", headers=headers, json=llm_payload, timeout=30)
        if r.status_code not in (200, 201):
            print(f"  [-] LLM creation failed: {r.status_code} - {r.text[:100]}")
            return None
        llm_data = r.json()
        llm_id = llm_data.get("llm_id")
        print(f"  [+] Created LLM: {llm_id}")
    except Exception as e:
        print(f"  [!] Error creating LLM: {e}")
        return None

    # Step 2: Create agent with LLM
    agent_payload = {
        "agent_name": f"MBM-{niche['name'].replace(' ', '-')}-{datetime.now().strftime('%H%M')}",
        "voice_id": voice_id,
        "response_engine": {
            "type": "retell-llm",
            "llm_id": llm_id
        }
    }

    try:
        r = requests.post("https://api.retellai.com/create-agent", headers=headers, json=agent_payload, timeout=30)
        if r.status_code in (200, 201):
            data = r.json()
            agent_id = data.get("agent_id", "unknown")
            return {
                "niche": niche["name"],
                "agent_id": agent_id,
                "llm_id": llm_id,
                "voice_id": voice_id,
                "rate_per_min": niche["rate"],
                "tags": niche["tags"],
                "deployed_at": datetime.now().isoformat(),
                "status": "deployed"
            }
        else:
            print(f"  [-] Failed: {r.status_code} - {r.text[:100]}")
            return None
    except Exception as e:
        print(f"  [!] Error: {e}")
        return None


def generate_one():
    """Generate and deploy one agent"""
    niche = get_next_niche()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Creating agent for: {niche['name']}")

    result = create_agent(niche)
    if result:
        deployed = load_deployed()
        deployed.append(result)
        save_deployed(deployed)
        print(f"  [+] Deployed: {result['agent_id']} (${result['rate_per_min']}/min)")
        print(f"  [+] Total deployed: {len(deployed)}")
        return result
    return None


def run_loop():
    """Generate agents every 15 minutes"""
    print(f"\n{'='*50}")
    print(f"  MBM VOICE AGENT FACTORY")
    print(f"  Generating new agent every 15 minutes")
    print(f"  Press Ctrl+C to stop")
    print(f"{'='*50}\n")

    while True:
        result = generate_one()
        if result:
            print(f"  Next agent in 15 minutes...\n")
        else:
            print(f"  Retrying in 5 minutes...\n")
            time.sleep(300)
            continue

        time.sleep(900)  # 15 minutes


def show_status():
    """Show all deployed agents"""
    deployed = load_deployed()
    if not deployed:
        print("[!] No agents deployed yet")
        return

    print(f"\n{'='*60}")
    print(f"  MBM DEPLOYED VOICE AGENTS ({len(deployed)} total)")
    print(f"{'='*60}\n")

    total_rate = 0
    for i, agent in enumerate(deployed, 1):
        print(f"  {i}. {agent['niche']}")
        print(f"     ID: {agent['agent_id']}")
        print(f"     Rate: ${agent['rate_per_min']}/min")
        print(f"     Tags: {', '.join(agent['tags'])}")
        print(f"     Deployed: {agent['deployed_at']}")
        print()
        total_rate += agent['rate_per_min']

    print(f"{'='*60}")
    print(f"  Total agents: {len(deployed)}")
    print(f"  Combined rate: ${total_rate:.2f}/min")
    print(f"  Hourly potential: ${total_rate * 60:.2f}/hr (if all active)")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="MBM Voice Agent Factory")
    parser.add_argument("--once", action="store_true", help="Generate 1 agent now")
    parser.add_argument("--loop", action="store_true", help="Generate every 15 minutes")
    parser.add_argument("--status", action="store_true", help="Show deployed agents")
    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.loop:
        run_loop()
    elif args.once:
        generate_one()
    else:
        generate_one()


if __name__ == "__main__":
    main()
