"""
Interactive Direct Phone Caller
================================
Mission: Interactive CLI dialer that lets you select a prospect (1-10) or type
any phone number to place a live outbound call via Twilio (+1 646-846-8822).
"""

import os
import sys
import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / 'logs'
TONIGHT_FILE = LOGS_DIR / 'tonight_10_call_list_skip_traced.json'

TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "+16619909068")


def main():
    print("============================================================")
    print("[DIALER] CONTECH AI AGENTIC TEAMZ INTERACTIVE PHONE DIALER (1,000 FREE MINS ACTIVE)")
    print("============================================================")
    print(f"Caller ID: {TWILIO_PHONE_NUMBER}")

    if not TONIGHT_FILE.exists():
        print("Error: tonight_10_call_list_skip_traced.json not found.")
        return

    with open(TONIGHT_FILE, 'r', encoding='utf-8') as f:
        prospects = json.load(f)

    print("\nSelect a prospect to call (1-10) or enter custom phone number:\n")
    for p in prospects:
        print(f"  [{p['rank']}] {p['prospect_name']} — {p['primary_phone']} | {p['city']} (${p['est_commission_profit']} profit)")

    print("\n------------------------------------------------------------")
    choice = input("Enter choice (1-10) or phone number (e.g. +16025551312): ").strip()

    target_phone = ""
    target_name = "Prospect"

    if choice.isdigit() and 1 <= int(choice) <= len(prospects):
        selected = prospects[int(choice) - 1]
        target_phone = selected['primary_phone_raw']
        target_name = selected['prospect_name']
    elif choice:
        target_phone = choice
        target_name = "Custom Prospect"
    else:
        # Default to Mark Johnson
        target_phone = prospects[0]['primary_phone_raw']
        target_name = prospects[0]['prospect_name']

    print(f"\n[DIALER] Dialing {target_name} ({target_phone}) from {TWILIO_PHONE_NUMBER}...")

    sys.path.append(str(BASE_DIR))
    from free_us_phone_dialer import place_outbound_call
    res = place_outbound_call(target_phone, target_name)
    
    print("\n============================================================")
    print(f"SUCCESS: CALL CONNECTED LIVE TO {target_name.upper()}!")
    print(f"Status: {res.get('status')} | Call ID: {res.get('call_id') or res.get('call_sid')}")
    print("============================================================")


if __name__ == "__main__":
    main()
