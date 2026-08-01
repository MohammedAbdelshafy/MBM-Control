"""
Extreme Sales High-Urgency Offer Blaster
=========================================
Mission: Dispatches high-urgency cash offer SMS pitches via Twilio (+16619909068)
and logs Telegram instant buy notifications for immediate cash settlement.
"""

import os
import sys
import json
import time
from pathlib import Path
from twilio.rest import Client

BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / 'logs'
TONIGHT_FILE = LOGS_DIR / 'tonight_10_call_list_skip_traced.json'

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "AC03c0fb6f1a1775d7385c364af597c999")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "32b051acb02af4cbaad0fe0c1ca551a8")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "+16619909068")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "8871015419:AAHXRLkEJlQEwdUiZWIjUoCUofrtbpraA34")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "6617518949")


def dispatch_sales_blast():
    print("[EXTREME SALES BLASTER] Dispatching High-Urgency SMS Cash Offers...")

    if not TONIGHT_FILE.exists():
        print("Error: tonight_10_call_list_skip_traced.json not found.")
        return

    with open(TONIGHT_FILE, 'r', encoding='utf-8') as f:
        prospects = json.load(f)

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    sent_count = 0

    for p in prospects[:5]:
        first_name = p['prospect_name'].split()[0]
        sms_text = (
            f"Hi {first_name}! Big Moe Shafy here with Contech AI. "
            f"We have a firm cash offer of {p['asking_price']} NET for {p['property_address']}. "
            f"Zero agent fees, zero repairs, 7-day close. "
            f"Call me back directly at +16619909068 or reply YES to lock in your payout today!"
        )

        print(f"  [SMS] Dispatching to {p['prospect_name']} ({p['primary_phone']})...")
        try:
            message = client.messages.create(
                body=sms_text,
                from_=TWILIO_PHONE_NUMBER,
                to=p['primary_phone_raw']
            )
            sent_count += 1
            print(f"    └─ Sent! Message SID: {message.sid}")
        except Exception as e:
            err_msg = str(e).encode('ascii', errors='replace').decode('ascii')
            print(f"    - Twilio SMS Notice: {err_msg}")

    # Send Telegram Sales Alert
    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        tg_text = (
            f"<b>🚀 EXTREME SALES BLASTER EXECUTED 🚀</b>\n\n"
            f"👤 <b>Closer</b>: Big Moe Shafy\n"
            f"🏢 <b>Company</b>: Contech AI Agentic Teamz\n"
            f"📱 <b>Caller ID</b>: +1 (661) 990-9068\n"
            f"📨 <b>High-Urgency Cash Offers Dispatched</b>: {sent_count} Top Prospects\n"
            f"💰 <b>Est. Commission Pipeline</b>: $178,500.00\n\n"
            f"🔗 <b>Dashboard</b>: http://localhost:5173/voice-agents"
        )
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": tg_text, "parse_mode": "HTML"}, timeout=5)
    except Exception:
        pass

    print(f"[EXTREME SALES BLASTER] COMPLETE: Processed {len(prospects[:5])} top targets.")


if __name__ == "__main__":
    dispatch_sales_blast()
