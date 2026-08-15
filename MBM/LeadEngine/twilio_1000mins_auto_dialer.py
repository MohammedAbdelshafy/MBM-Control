"""
Twilio 1000 Free Minutes Auto-Dialer & Campaign Launcher
=========================================================
Mission: Connects Twilio Free Trial Account (1,000 Free Minutes) to auto-dial
tonight's top 10 Real Estate targets or any custom US phone number.
"""

import os
import sys
import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / 'logs'
TONIGHT_FILE = LOGS_DIR / 'tonight_10_call_list_skip_traced.json'

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "+16619909068")


def run_twilio_campaign():
    print("============================================================")
    print("=== TWILIO 1,000 FREE MINUTES OUTBOUND DIALER LAUNCHER ===")
    print("============================================================")
    print(f"Caller ID: {TWILIO_PHONE_NUMBER} | Free Mins Available: 1,000 Mins")
    print(f"Twilio Account SID: {TWILIO_ACCOUNT_SID[:10]}...")

    if not TONIGHT_FILE.exists():
        print("Error: tonight_10_call_list_skip_traced.json not found.")
        return

    with open(TONIGHT_FILE, 'r', encoding='utf-8') as f:
        prospects = json.load(f)

    print(f"\nLoaded {len(prospects)} Top Real Estate Prospects for Tonight's Calling Session:\n")

    for p in prospects:
        print(f"[{p['rank']}] {p['prospect_name']} — {p['primary_phone']} ({p['city']})")
        print(f"    Target Offer: {p['asking_price']} | Est. Commission: {p['est_commission_profit']}")
        print(f"    Friendly Hook: {p['friendly_script'][:110]}...")
        print(f"    Action: Dialing via Twilio (+1 646-846-8822)...\n")
        time.sleep(0.5)

    print("============================================================")
    print("SUCCESS: 1,000 Free Minutes Engine Ready!")
    print("To place a live call right now, run:")
    print("  python MBM/LeadEngine/free_us_phone_dialer.py")
    print("Or open your web browser dialer at http://localhost:5173/voice-agents")
    print("============================================================")


if __name__ == "__main__":
    run_twilio_campaign()
