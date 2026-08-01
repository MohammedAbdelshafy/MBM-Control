#!/usr/bin/env python3
"""
Twilio + Retell Bridge
Makes outbound calls via Twilio and transfers to Retell AI agents.
Uses your 1000 free Twilio minutes.

Usage:
  python twilio_retell_bridge.py --call 4696584582 --agent seller
  python twilio_retell_bridge.py --call-all          # Call all pipeline leads
  python twilio_retell_bridge.py --status             # Check Twilio balance
"""

import os
import sys
import json
import csv
import argparse
import time
from pathlib import Path
from datetime import datetime

try:
    from twilio.rest import Client as TwilioClient
except ImportError:
    os.system(f"{sys.executable} -m pip install twilio -q")
    from twilio.rest import Client as TwilioClient

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

ROOT = Path(__file__).resolve().parent.parent.parent
PIPELINE = ROOT / "MBM" / "Pipeline" / "pipeline.csv"
LOGS_DIR = ROOT / "MBM" / "LeadEngine" / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Twilio credentials
TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_PHONE_NUMBER")

# Retell credentials
RETELL_API_KEY = os.getenv("RETELL_API_KEY")

# Agent mapping
AGENTS = {
    "seller": "agent_00bb14caed46feaddd75526ce2",
    "buyer": "agent_1cf38b194ed2d0cf9842ba82ee",
    "pre foreclosure": "agent_3404c7c4a6f7b1448145fbbdd9",
    "commercial": "agent_ec2545ec4ba59441a07608623b",
    "referral": "agent_8e178801707abe5236c469cc00",
    "ecommerce": "agent_43b5f21d2663151d439c3c699d",
}

# Script prompts for each agent type
SCRIPTS = {
    "seller": {
        "greeting": "Hi, this is Sarah from MBM Property Solutions. I'm reaching out regarding your property. Are you still interested in selling?",
        "questions": ["What's the address?", "What's your timeline?", "Would you consider a cash offer?"],
    },
    "buyer": {
        "greeting": "Hi, this is James from MBM Property Solutions. I'm reaching out about your property search. Are you still looking to buy?",
        "questions": ["What's your budget?", "What area?", "Are you pre-approved?"],
    },
    "pre foreclosure": {
        "greeting": "Hi, this is Maria from MBM Property Solutions. We help homeowners in pre-foreclosure. Are you still in need of assistance?",
        "questions": ["When is your auction date?", "How much do you owe?", "Would you accept a cash offer?"],
    },
}


def get_twilio_client():
    if not TWILIO_SID or not TWILIO_TOKEN:
        print("[!] TWILIO_ACCOUNT_SID or TWILIO_AUTH_TOKEN not set in .env")
        return None
    return TwilioClient(TWILIO_SID, TWILIO_TOKEN)


def check_balance():
    client = get_twilio_client()
    if not client:
        return

    account = client.api.accounts(TWILIO_SID).fetch()
    print(f"\n{'='*50}")
    print(f"  TWILIO ACCOUNT STATUS")
    print(f"{'='*50}")
    print(f"  Account: {account.friendly_name}")
    print(f"  Status: {account.status}")
    print(f"  Balance: {account.balance}")
    print(f"  Phone: {TWILIO_FROM}")
    print(f"{'='*50}\n")


def call_lead(phone, agent_type="seller", lead_info=None):
    """Make an outbound call via Twilio with TwiML that connects to Retell"""
    client = get_twilio_client()
    if not client:
        return None

    # Clean phone number
    phone = phone.replace("-", "").replace("(", "").replace(")", "").replace(" ", "")
    if not phone.startswith("+"):
        phone = "+1" + phone

    agent_id = AGENTS.get(agent_type, AGENTS["seller"])
    script = SCRIPTS.get(agent_type, SCRIPTS["seller"])

    # Create TwiML that connects to Retell via SIP
    # This uses Twilio's <Connect> verb to bridge to Retell's SIP endpoint
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="Polly.Matthew">{script['greeting']}</Say>
    <Pause length="2"/>
    <Connect>
        <Sip>sip:{agent_id}@sip.retellai.com</Sip>
    </Connect>
</Response>"""

    try:
        call = client.calls.create(
            to=phone,
            from_=TWILIO_FROM,
            twiml=twiml,
            timeout=30,
            record=True,
            machine_detection="Enable",
            status_callback="https://webhook.site/unique-url",
            status_callback_event=["initiated", "ringing", "answered", "completed"],
        )

        result = {
            "call_sid": call.sid,
            "to": phone,
            "from": TWILIO_FROM,
            "agent_type": agent_type,
            "status": call.status,
            "timestamp": datetime.now().isoformat(),
            "lead_info": lead_info,
        }

        print(f"  [+] Call initiated: {call.sid}")
        print(f"  [+] To: {phone}")
        print(f"  [+] Agent: {agent_type}")
        print(f"  [+] Status: {call.status}")

        return result

    except Exception as e:
        print(f"  [!] Error calling {phone}: {e}")
        return None


def call_all_leads(agent_type=None):
    """Call all leads in the pipeline"""
    if not PIPELINE.exists():
        print(f"[!] Pipeline file not found: {PIPELINE}")
        return

    leads = []
    with open(PIPELINE, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            phone = row.get("phone", "").strip()
            if phone and phone != "phone":
                leads.append({
                    "company": row.get("company", "Unknown"),
                    "phone": phone,
                    "email": row.get("email", ""),
                    "solution": row.get("solution", ""),
                    "notes": row.get("notes", ""),
                })

    if not leads:
        print("[!] No leads found")
        return

    print(f"\n{'='*60}")
    print(f"  CALLING {len(leads)} LEADS")
    print(f"  Using 1000 free Twilio minutes")
    print(f"{'='*60}\n")

    results = []
    for i, lead in enumerate(leads, 1):
        # Auto-detect agent type based on lead info
        if not agent_type:
            if "sell" in lead.get("solution", "").lower() or "foreclosure" in lead.get("notes", "").lower():
                auto_agent = "seller"
            elif "buy" in lead.get("solution", "").lower():
                auto_agent = "buyer"
            else:
                auto_agent = "seller"
        else:
            auto_agent = agent_type

        print(f"[{i}/{len(leads)}] {lead['company']}")
        print(f"  Phone: {lead['phone']}")
        print(f"  Agent: {auto_agent}")

        result = call_lead(lead["phone"], auto_agent, lead)
        if result:
            results.append(result)
        print()

        # Rate limit - 1 call per 2 seconds
        time.sleep(2)

    # Save results
    output_file = LOGS_DIR / f"twilio_calls_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2)

    print(f"{'='*60}")
    print(f"  Results saved to {output_file.name}")
    print(f"  Total calls: {len(results)}")
    print(f"  Minutes used: ~{len(results) * 2} min (est. 2 min per call)")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(description="Twilio + Retell Bridge")
    parser.add_argument("--call", "-c", help="Phone number to call")
    parser.add_argument("--agent", "-a", default="seller", choices=list(AGENTS.keys()))
    parser.add_argument("--call-all", action="store_true", help="Call all pipeline leads")
    parser.add_argument("--status", action="store_true", help="Check Twilio balance")
    args = parser.parse_args()

    if args.status:
        check_balance()
    elif args.call_all:
        call_all_leads(args.agent)
    elif args.call:
        result = call_lead(args.call, args.agent)
        if result:
            print(f"\n[+] Call initiated successfully!")
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
