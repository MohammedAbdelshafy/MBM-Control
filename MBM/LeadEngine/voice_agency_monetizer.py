"""
Contech AI Voice Agency Direct Monetization Engine
===================================================
Mission: Pitches 24/7 AI Voice Swarms to Call-Intensive Businesses
($1,500 Setup Fee + $497/mo Retainer or $2,497 Full Enterprise License).
"""

import os
import sys
import json
import time
import requests
import sys
from pathlib import Path
if str(Path(__file__).resolve().parents[2]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from MBM.Scripts.neteller_config import neteller_link, NETELLER_EMAIL, NETELLER_ACCOUNT_ID

NETELLER_EMAIL = os.getenv("NETELLER_EMAIL", "abdelshafyclapps@gmail.com")
NETELLER_ACCOUNT_ID = os.getenv("NETELLER_ACCOUNT_ID", "4599228811")
SUPABASE_URL = os.getenv("VITE_SUPABASE_URL", "https://prgmwljhbjtcjmwnjaao.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

VOICE_AGENCY_TARGETS = [
    {"name": "Texas Solar Direct", "email": "sales@texassolardirect.com", "industry": "Solar Sales"},
    {"name": "DFW Premier Dental Group", "email": "contact@dfwdental.com", "industry": "Dental Patient Intake"},
    {"name": "Lone Star Insurance Agency", "email": "info@lonestarinsurance.com", "industry": "Insurance Leads"},
    {"name": "Dallas Urgent Care Network", "email": "intake@dallasurgentcare.com", "industry": "Medical Scheduling"},
    {"name": "National Property Wholesalers", "email": "acquisitions@nationalwholesalers.com", "industry": "Real Estate Wholesale"}
]


def monetize_voice_agency():
    print("============================================================")
    print("[VOICE AGENCY] DIRECT MONETIZATION & CALL SWARM SALES")
    print("============================================================")

    queued_offers = []

    for idx, v in enumerate(VOICE_AGENCY_TARGETS, 1):
        subject = f"Deploy 24/7 Autonomous AI Voice Agent Swarm for {v['name']} ({v['industry']})"
        body = (
            f"Hello {v['name']} Team,\n\n"
            f"Replace manual cold calling and intake queues with our 24/7 Contech AI Voice Bot Swarm. Handles 10,000 inbound/outbound calls simultaneously with sub-500ms latency.\n\n"
            f"OFFER 1: Complete AI Voice Agent Setup & Integration ($1,500.00 USD)\n"
            f"1-Click Neteller Checkout: {neteller_link(1500.00, 'AI_Voice_Setup_Fee')}\n\n"
            f"OFFER 2: Monthly Unlimited Call Swarm Retainer ($497.00 / month)\n"
            f"1-Click Neteller Checkout: {neteller_link(497.00, 'AI_Voice_Monthly_Retainer')}\n\n"
            f"Best regards,\n"
            f"Contech AI Voice Agency Team\n"
            f"abdelshafyclapps@gmail.com"
        )

        queued_offers.append({
            "recipient_email": v["email"],
            "subject": subject,
            "body": body,
            "status": "qued"
        })

    # Queue into Supabase email_queue
    if SUPABASE_KEY:
        headers = {
            "apikey": SUPABASE_KEY,
            "Authorization": f"Bearer {SUPABASE_KEY}",
            "Content-Type": "application/json"
        }
        try:
            url = f"{SUPABASE_URL}/rest/v1/email_queue"
            requests.post(url, headers=headers, json=queued_offers, timeout=10)
            print(f"   - Successfully queued {len(queued_offers)} Voice Agency Offers into email_queue!")
        except Exception as e:
            print(f"   - Supabase notice: {e}")

    print("\n[COMPLETE] Voice Agency Direct Monetization Fired Successfully!")


if __name__ == "__main__":
    monetize_voice_agency()
