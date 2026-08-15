"""
Send Final Enhanced MBM Dialer Links & Intelligence to Telegram
===============================================================
Pushes the verified live links, local Wi-Fi IP, and high-ticket
closing cheat sheet directly to the user's Telegram.
"""

import os
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent

CHAT_ID_FILE = BASE_DIR.parent / "Config" / "telegram_chat_id.txt"

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

if not CHAT_ID and CHAT_ID_FILE.exists():
    try:
        with open(CHAT_ID_FILE, "r", encoding="utf-8") as f:
            CHAT_ID = f.read().strip()
    except Exception:
        pass


def send_telegram_alert():
    message_text = (
        "🚀 *FINAL ENHANCED MBM DIALER & REAL ESTATE ENGINE*\n\n"
        "📱 *DIRECT PHONE LINK (Same Wi-Fi)*:\n"
        "👉 http://192.168.8.92:5173\n\n"
        "💻 *DESKTOP LINK*:\n"
        "👉 http://localhost:5173\n\n"
        "🔒 *TAILSCALE SECURE LINK*:\n"
        "👉 http://100.70.189.91:5173\n\n"
        "🔥 *DATABASE STATS*:\n"
        "• Total Verified Leads: *712 Dial-Ready*\n"
        "• Real Estate Sellers: *199 Verified*\n"
        "• VIP Cash Buyers & Flippers: *30 Verified*\n"
        "• Healthcare Practices: *434 NPI Verified*\n\n"
        "⚡ *NEW LIVE FEATURES*:\n"
        "1. *Sub-second Groq Objection Handling Copilot* (Port 3005)\n"
        "2. *Cash Buyer 35% Below ARV Pitch Scripts*\n"
        "3. *Real Estate As-Is 7-Day Close Scripts*\n"
        "4. *Live Dial Velocity & Motivation Badges*\n\n"
        "💎 *Bloomberg Luxury Deal Terminal*:\n"
        "👉 `file:///c:/Users/omare/OneDrive/Desktop/AI/MBM/LeadEngine/InstitutionalRealEstate/luxury_deal_terminal.html`\n\n"
        "📊 *Salesforce AI OS CRM*:\n"
        "👉 `file:///c:/Users/omare/OneDrive/Desktop/AI/MBM/SalesforceOS/salesforce_crm.html`"
    )

    print("=" * 70)
    print("  📱 MBM DIALER TELEGRAM NOTIFICATION DISPATCHER")
    print("=" * 70)
    print(f"  Target Chat ID: {CHAT_ID or 'Not Set'}")
    print(f"  Bot Token Present: {'YES' if TOKEN else 'NO (Set TELEGRAM_BOT_TOKEN in .env)'}")
    print("-" * 70)

    if TOKEN and CHAT_ID:
        try:
            url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            payload = {
                "chat_id": CHAT_ID,
                "text": message_text,
                "parse_mode": "Markdown",
                "disable_web_page_preview": False
            }
            req = urllib.request.Request(
                url,
                data=urllib.parse.urlencode(payload).encode("utf-8"),
                headers={"Content-Type": "application/x-www-form-urlencoded"}
            )
            resp = urllib.request.urlopen(req, timeout=10)
            res_data = json.loads(resp.read().decode("utf-8"))
            if res_data.get("ok"):
                print("  ✅ Successfully dispatched directly to your Telegram chat!")
            else:
                print(f"  [WARN] Telegram API error: {res_data}")
        except Exception as e:
            print(f"  [WARN] Telegram send exception: {e}")
    else:
        print("  ℹ️ TELEGRAM_BOT_TOKEN not configured in environment — providing formatted dispatch below.")

    print("\n" + message_text + "\n")
    print("=" * 70)


if __name__ == "__main__":
    send_telegram_alert()
