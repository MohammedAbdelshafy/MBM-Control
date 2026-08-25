#!/usr/bin/env python3
"""
MBM Voice Agent Factory
Generates and deploys NEW voice agents to Retell AI.

Usage:
  python agent_factory.py --once
  python agent_factory.py --loop
  python agent_factory.py --deploy
  python agent_factory.py --status
"""

import json
import os
import sys
import time
import random
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

ROOT = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = ROOT / "MBM" / "LeadEngine" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)
AGENTS_FILE = LOGS_DIR / "factory_agents.json"
DEPLOYED_FILE = LOGS_DIR / "deployed_agents.json"

RETELL_API_KEY = os.getenv("RETELL_API_KEY")

# Keep this aligned with the last known-good production fix.
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
        "hook": "Hi! I'm following up on your insurance claim. Do you still need assistance with the claims process?",
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
]


def load_deployed():
    try:
        if DEPLOYED_FILE.exists():
            return json.loads(DEPLOYED_FILE.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[!] Failed loading deployed agents: {e}")
    return []


def save_deployed(data):
    DEPLOYED_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_next_niche():
    deployed = load_deployed()
    used = {a.get("niche") for a in deployed}
    for niche in NICHES:
        if niche["name"] not in used:
            return niche
    return random.choice(NICHES)


def create_agent(niche):
    """Create a new Retell LLM and attach it to a voice agent."""
    if not RETELL_API_KEY:
        print("[!] RETELL_API_KEY not set")
        return None

    headers = {
        "Authorization": f"Bearer {RETELL_API_KEY}",
        "Content-Type": "application/json",
    }

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

    llm_payload = {
        "model": "gemini-2.5-flash-lite",
        "general_prompt": prompt,
        "start_speaker": "agent",
        "begin_message": niche["hook"],
    }

    try:
        r = requests.post(
            "https://api.retellai.com/create-retell-llm",
            headers=headers,
            json=llm_payload,
            timeout=30,
        )
        if r.status_code not in (200, 201):
            print(f"  [-] LLM creation failed: {r.status_code} - {r.text[:500]}")
            return None
        llm_id = r.json().get("llm_id")
        if not llm_id:
            print(f"  [-] LLM creation returned no llm_id: {r.text[:500]}")
            return None
        print(f"  [+] Created LLM: {llm_id}")
    except Exception as e:
        print(f"  [!] Error creating LLM: {e}")
        return None

    # Retell documents that the agent must attach a previously-created response
    # engine. Give the control plane a small propagation window before attach.
    time.sleep(5)

    agent_payload = {
        "agent_name": f"MBM-{niche['name'].replace(' ', '-')}-{datetime.now().strftime('%H%M%S')}",
        "voice_id": voice_id,
        "response_engine": {
            "type": "retell-llm",
            "llm_id": llm_id,
        },
    }

    last_status = None
    last_body = ""
    for attempt in range(5):
        try:
            r = requests.post(
                "https://api.retellai.com/create-agent",
                headers=headers,
                json=agent_payload,
                timeout=30,
            )
            last_status = r.status_code
            last_body = r.text
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
                    "status": "deployed",
                }

            # Retry control-plane/transient failures. Do not hide deterministic
            # validation/auth failures such as 400/401/422.
            if r.status_code in (404, 429, 500, 502, 503, 504) and attempt < 4:
                wait = 5 * (attempt + 1)
                print(
                    f"  [~] Retell create-agent {r.status_code} "
                    f"(attempt {attempt + 1}/5), retrying in {wait}s"
                )
                time.sleep(wait)
                continue

            print(f"  [-] create-agent failed: {r.status_code} - {r.text[:1000]}")
            return None
        except Exception as e:
            if attempt < 4:
                wait = 5 * (attempt + 1)
                print(f"  [~] create-agent exception: {e}; retrying in {wait}s")
                time.sleep(wait)
                continue
            print(f"  [!] create-agent exhausted retries: {e}")
            return None

    print(f"  [-] Failed after retries: {last_status} - {last_body[:1000]}")
    return None


def generate_one(niche=None):
    if niche is None:
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
    print("\n" + "=" * 50)
    print("  MBM VOICE AGENT FACTORY")
    print("  Generating new agent every 15 minutes")
    print("=" * 50 + "\n")
    while True:
        result = generate_one()
        if result:
            print("  Next agent in 15 minutes...\n")
            time.sleep(900)
        else:
            print("  Retrying in 5 minutes...\n")
            time.sleep(300)


def show_status():
    deployed = load_deployed()
    if not deployed:
        print("[!] No agents deployed yet")
        return
    print("\n" + "=" * 60)
    print(f"  MBM DEPLOYED VOICE AGENTS ({len(deployed)} total)")
    print("=" * 60 + "\n")
    total_rate = 0
    for i, agent in enumerate(deployed, 1):
        print(f"  {i}. {agent['niche']}")
        print(f"     ID: {agent['agent_id']}")
        print(f"     Rate: ${agent['rate_per_min']}/min")
        print(f"     Tags: {', '.join(agent['tags'])}")
        print(f"     Deployed: {agent['deployed_at']}")
        print()
        total_rate += agent['rate_per_min']
    print("=" * 60)
    print(f"  Total agents: {len(deployed)}")
    print(f"  Combined rate: ${total_rate:.2f}/min")
    print(f"  Potential monthly: ${total_rate * 60 * 8 * 22:,.0f}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--deploy", action="store_true")
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--count", type=int, default=1)
    args = parser.parse_args()

    if args.status:
        show_status()
    elif args.loop:
        run_loop()
    elif args.deploy:
        for _ in range(max(1, args.count)):
            generate_one()
    else:
        for _ in range(max(1, args.count)):
            generate_one()


if __name__ == "__main__":
    main()
