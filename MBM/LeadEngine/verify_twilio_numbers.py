#!/usr/bin/env python3
"""
Verify phone numbers on Twilio trial account.
Run this after verifying numbers in the Twilio console.

Usage:
  python verify_twilio_numbers.py --check    # Check which numbers are verified
  python verify_twilio_numbers.py --call-all # Call all leads after verification
"""

import os
import sys
import json
import csv
import argparse
from pathlib import Path

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

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_PHONE_NUMBER")


def get_client():
    return TwilioClient(TWILIO_SID, TWILIO_TOKEN)


def check_verified_numbers():
    client = get_client()
    outgoing = client.outgoing_caller_ids.list()
    
    print(f"\n{'='*50}")
    print(f"  VERIFIED CALLER IDS")
    print(f"{'='*50}")
    
    verified = []
    for caller_id in outgoing:
        status = "VERIFIED" if caller_id.verification_status == "approved" else "PENDING"
        print(f"  {caller_id.phone_number} - {status}")
        if caller_id.verification_status == "approved":
            verified.append(caller_id.phone_number)
    
    print(f"\n  Total verified: {len(verified)}")
    print(f"{'='*50}\n")
    
    return verified


def verify_number(phone):
    """Start verification for a phone number"""
    client = get_client()
    phone = phone.replace("-", "").replace("(", "").replace(")", "").replace(" ", "")
    if not phone.startswith("+"):
        phone = "+1" + phone
    
    try:
        # This sends a verification SMS or call
        verification = client.verify.services(
            os.getenv("TWILIO_VERIFY_SERVICE_SID", "VA" + "x" * 32)
        ).verifications.create(
            to=phone,
            channel="sms"
        )
        print(f"  [+] Verification sent to {phone} via SMS")
        return True
    except Exception as e:
        print(f"  [!] Could not send verification: {e}")
        print(f"  [!] Please verify manually in Twilio Console:")
        print(f"      https://console.twilio.com/us1/develop/phone-numbers/manage/verified")
        return False


def main():
    parser = argparse.ArgumentParser(description="Verify Twilio numbers")
    parser.add_argument("--check", action="store_true", help="Check verified numbers")
    parser.add_argument("--verify", help="Verify a specific number")
    parser.add_argument("--call-all", action="store_true", help="Call all leads")
    args = parser.parse_args()

    if args.check:
        verified = check_verified_numbers()
        if len(verified) == 0:
            print("[!] No verified numbers. Go to Twilio Console to verify.")
    elif args.verify:
        verify_number(args.verify)
    elif args.call_all:
        verified = check_verified_numbers()
        if len(verified) == 0:
            print("[!] No verified numbers. Cannot make calls.")
            return
        
        # Import and run the bridge
        sys.path.insert(0, str(Path(__file__).parent))
        from twilio_retell_bridge import call_all_leads
        call_all_leads()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
