#!/usr/bin/env python3
"""
Bulk verify phone numbers on Twilio trial account.
Sends verification SMS to each number.

Usage: python bulk_verify_twilio.py
"""

import os
import sys
import json
import csv
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

TWILIO_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_FROM = os.getenv("TWILIO_PHONE_NUMBER")

# All unique phone numbers from your runs
NUMBERS = [
    # Pipeline leads (4)
    {"phone": "+14696584582", "name": "PipHouse LLC", "source": "pipeline"},
    {"phone": "+14692731235", "name": "Swift Home Solutions", "source": "pipeline"},
    {"phone": "+19727341612", "name": "New Western", "source": "pipeline"},
    {"phone": "+18173001132", "name": "DFW REI Club", "source": "pipeline"},
    # WhatsApp leads (9 more)
    {"phone": "+12149297576", "name": "3134 Arizona Ave seller", "source": "whatsapp"},
    {"phone": "+18179888547", "name": "Joel - RE agent/investor", "source": "whatsapp"},
    {"phone": "+12145149615", "name": "1825 Canelo Dr seller", "source": "whatsapp"},
    {"phone": "+18173663324", "name": "Velma - 1900 Ridge Oak", "source": "whatsapp"},
    {"phone": "+14696603146", "name": "Miguel - 2106 Holland St", "source": "whatsapp"},
    {"phone": "+14694364884", "name": "Diamond Acquisitions", "source": "whatsapp"},
    {"phone": "+15124004457", "name": "Calvin - Turner & Partners", "source": "whatsapp"},
    {"phone": "+14694614209", "name": "DFW investor", "source": "whatsapp"},
    {"phone": "+12142841222", "name": "Rylie - Altura Homes", "source": "whatsapp"},
    # PainPoints (3 more unique)
    {"phone": "+12149089188", "name": "Steve Hendry Homes", "source": "painpoints"},
    {"phone": "+12142336158", "name": "ULR Properties Dallas", "source": "painpoints"},
    {"phone": "+12145998997", "name": "LBJ Station", "source": "painpoints"},
]


def verify_all():
    client = TwilioClient(TWILIO_SID, TWILIO_TOKEN)

    # Check current verified numbers
    existing = client.outgoing_caller_ids.list()
    verified_phones = set()
    for c in existing:
        try:
            verified_phones.add(c.phone_number)
        except:
            pass

    # Create or get Verify service
    services = client.verify.v2.services.list()
    if services:
        verify_service = services[0]
    else:
        verify_service = client.verify.v2.services.create(friendly_name="MBM Lead Verification")

    print(f"\n{'='*60}")
    print(f"  TWILIO BULK NUMBER VERIFICATION")
    print(f"{'='*60}")
    print(f"  Already on account: {len(verified_phones)}")
    print(f"  Numbers to verify: {len(NUMBERS)}")
    print(f"{'='*60}\n")

    # Filter out already verified
    to_verify = [n for n in NUMBERS if n["phone"] not in verified_phones]

    if not to_verify:
        print("[+] All numbers are already verified!")
        return

    print(f"[*] Verifying {len(to_verify)} numbers...\n")

    verified_count = 0
    failed_count = 0

    for i, num in enumerate(to_verify, 1):
        phone = num["phone"]
        name = num["name"]
        source = num["source"]

        print(f"[{i}/{len(to_verify)}] {name}")
        print(f"  Phone: {phone}")
        print(f"  Source: {source}")

        try:
            # Send verification SMS
            verification = client.verify.v2.services(verify_service.sid).verifications.create(
                to=phone,
                channel="sms"
            )
            print(f"  [+] Verification SMS sent! Status: {verification.status}")
            verified_count += 1
        except Exception as e:
            print(f"  [!] Error: {e}")
            failed_count += 1

        print()

    # Summary
    print(f"{'='*60}")
    print(f"  VERIFICATION SUMMARY")
    print(f"{'='*60}")
    print(f"  Total numbers: {len(NUMBERS)}")
    print(f"  Already verified: {len(verified_phones)}")
    print(f"  New verifications sent: {verified_count}")
    print(f"  Failed: {failed_count}")
    print(f"{'='*60}")
    print(f"\n  [!] IMPORTANT: Each number must receive the SMS code")
    print(f"  [!] and be verified in the Twilio console to work.")
    print(f"  [!] Console: https://console.twilio.com/us1/develop/phone-numbers/manage/verified")
    print(f"{'='*60}\n")

    # Save status
    status = {
        "total": len(NUMBERS),
        "already_verified": len(verified_phones),
        "new_verifications": verified_count,
        "failed": failed_count,
        "numbers": NUMBERS,
        "verified_phones": list(verified_phones),
    }
    with open(ROOT / "MBM" / "LeadEngine" / "logs" / "twilio_verification_status.json", "w") as f:
        json.dump(status, f, indent=2)


if __name__ == "__main__":
    verify_all()
