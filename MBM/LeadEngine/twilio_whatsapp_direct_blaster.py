"""
Phound SMS Direct Blaster Agent
================================
Blasts high-ticket sales messages from your Phound number containing 1-click
Neteller checkout links for $5,000 Real Estate Deals and $2,497/mo Agency
Licenses. Twilio is no longer used — Phound is the telephony layer.
"""

import os
import sys
import json
import time
from pathlib import Path
from dotenv import load_dotenv
import sys
from pathlib import Path
if str(Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from MBM.Scripts.neteller_config import neteller_link, NETELLER_EMAIL, NETELLER_ACCOUNT_ID

BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)
WHATSAPP_LOG = LOGS_DIR / 'whatsapp_blaster_history.json'

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

MY_PHONE_NUMBER = os.getenv("PHOUND_PHONE_NUMBER", "+16619909068")
NETELLER_EMAIL = os.getenv("NETELLER_EMAIL", "abdelshafyclapps@gmail.com")
NETELLER_ACCOUNT_ID = os.getenv("NETELLER_ACCOUNT_ID", "4599228811")

TARGET_NUMBERS = [
    {"name": "New Western Acquisitions", "phone": "+12145550199", "offer_type": "wholesale"},
    {"name": "Swift Home Solutions", "phone": "+18175550188", "offer_type": "wholesale"},
    {"name": "DFW REI Club", "phone": "+18173001132", "offer_type": "wholesale"},
    {"name": "PipHouse LLC", "phone": "+12145550144", "offer_type": "lead_pack"},
    {"name": "Compass Agent Ops", "phone": "+12125550133", "offer_type": "agency"}
]


def blast_whatsapp_messages():
    print("============================================================")
    print(f"[PHOUND BLASTER] PREPARING FROM MY NUMBER ({MY_PHONE_NUMBER})")
    print("============================================================")

    dispatched = []

    for idx, target in enumerate(TARGET_NUMBERS, 1):
        if target["offer_type"] == "wholesale":
            msg_body = (
                f"Hi {target['name']},\n\n"
                f"We locked up exclusive wholesale rights for 2 off-market Dallas properties ($35,500 built-in equity).\n\n"
                f"Wholesale Rights ($5,000): {neteller_link(5000.00, 'Wholesale_Deal_Rights')}"
            )
        elif target["offer_type"] == "agency":
            msg_body = (
                f"Hi {target['name']},\n\n"
                f"Deploy our 24/7 Contech AI Voice Bot Swarm for your agency with 80% profit margins.\n\n"
                f"White-Label License ($2,497/mo): {neteller_link(2497.00, 'Agency_WhiteLabel_License')}"
            )
        else:
            msg_body = (
                f"Hi {target['name']},\n\n"
                f"Download 50 deep skip-traced DFW seller leads (Probate/Tax Delinquent) with primary phones & emails.\n\n"
                f"50 Lead Pack ($997): {neteller_link(997.00, '50_US_Lead_Pack')}"
            )

        prefill = f"https://web.phound.app/?phone={target['phone']}"
        print(f"\n[{idx}/{len(TARGET_NUMBERS)}] Preparing Phound message for {target['name']} ({target['phone']})...")

        record = {
            "target": target["name"],
            "phone": target["phone"],
            "from_number": MY_PHONE_NUMBER,
            "prefill": prefill,
            "message": msg_body,
            "timestamp": time.time()
        }
        dispatched.append(record)

    with open(WHATSAPP_LOG, "w", encoding="utf-8") as f:
        json.dump(dispatched, f, indent=2)

    print(f"\n[COMPLETE] Phound Blaster Prepared {len(dispatched)} Direct Messages from {MY_PHONE_NUMBER}!")
    print("Send each via the Phound app using the prefill links (logs/whatsapp_blaster_history.json).")


if __name__ == "__main__":
    blast_whatsapp_messages()
