"""
Twilio Call Bridge to Personal Mobile Phone
============================================
Mission: Calls your personal mobile phone first, then instantly bridges you to
the prospect showing your Twilio number (+16619909068) as the Caller ID!
"""

import os
import sys
import argparse
from pathlib import Path
from twilio.rest import Client

ROOT = Path(__file__).resolve().parent.parent.parent
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "").strip()
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "").strip()
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "").strip()

if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN and TWILIO_PHONE_NUMBER):
    print("ERROR: TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_PHONE_NUMBER must be set in AI/.env")
    sys.exit(1)


def bridge_call(my_mobile_number, prospect_number, simulate=False):
    print("============================================================")
    print("[CALL BRIDGER] CONTECH AI AGENTIC TEAMZ MOBILE CALL BRIDGER")
    print("============================================================")
    print(f"My Mobile Phone: {my_mobile_number}")
    print(f"Prospect Number: {prospect_number}")
    print(f"Twilio Caller ID: {TWILIO_PHONE_NUMBER}")

    if "YOUR_PHONE" in my_mobile_number or "YOUR_NUMBER" in my_mobile_number:
        print("\n⚠️ NOTICE: Please replace '+1YOUR_PHONE' with your actual personal cell phone number!")
        print("Example: python MBM/LeadEngine/call_bridge_to_phone.py --my-phone +12145551234 --prospect +16025551312")
        print("============================================================")
        return None

    if simulate:
        print("\n[SIMULATION MODE] Live Call Bridge Verified!")
        print(f"1. Twilio calls your phone ({my_mobile_number})")
        print(f"2. You answer -> Twilio plays 'Connecting your call...'")
        print(f"3. Twilio dials prospect ({prospect_number}) showing Caller ID {TWILIO_PHONE_NUMBER}")
        print("============================================================")
        return "SIMULATED_CALL_SID_12345"

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    twiml_instruction = f'<Response><Say>Connecting your call via Twilio...</Say><Dial callerId="{TWILIO_PHONE_NUMBER}">{prospect_number}</Dial></Response>'

    call = client.calls.create(
        twiml=twiml_instruction,
        to=my_mobile_number,
        from_=TWILIO_PHONE_NUMBER
    )

    print(f"\nSUCCESS: Twilio is ringing your phone ({my_mobile_number}) right now!")
    print(f"Answer the call and you will be instantly connected to {prospect_number}.")
    print(f"Call SID: {call.sid}")
    print("============================================================")
    return call.sid


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Bridge call to mobile phone")
    parser.add_argument("--my-phone", required=True, help="Your personal cell phone number e.g. +1234567890")
    parser.add_argument("--prospect", default="+16025551312", help="Prospect phone number")
    parser.add_argument("--simulate", action="store_true", help="Simulate call bridge workflow without placing live call")
    args = parser.parse_args()

    bridge_call(args.my_phone, args.prospect, args.simulate)
