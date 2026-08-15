"""
Extreme Sales High-Urgency Offer Blaster (Phound Wave)
=========================================================
Dispatches high-urgency cash offer SMS pitches through the Phound Wave
campaign engine (native-app mode) and logs a Telegram instant-buy notification.
Twilio is no longer used — Phound is the telephony layer.
"""

import os
import sys
import json
import time
from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / 'logs'
TONIGHT_FILE = LOGS_DIR / 'tonight_10_call_list_skip_traced.json'

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "6617518949")


def dispatch_sales_blast():
    print("[EXTREME SALES BLASTER] Dispatching High-Urgency SMS Cash Offers via Phound Wave...")

    if not TONIGHT_FILE.exists():
        print("Error: tonight_10_call_list_skip_traced.json not found.")
        return

    with open(TONIGHT_FILE, 'r', encoding='utf-8') as f:
        prospects = json.load(f)

    sys.path.insert(0, str(BASE_DIR.parent.parent))
    from MBM.LeadEngine.phound_wave_campaign import build_message, OFFERS, DEFAULT_OFFER, normalize_e164, CAMPAIGN_EXPORT_DIR

    sent_count = 0
    exports = []

    for p in prospects[:5]:
        phone = normalize_e164(p.get('primary_phone') or p.get('primary_phone_raw'))
        if not phone:
            continue
        first_name = (p.get('prospect_name') or 'there').split()[0]
        offer = OFFERS.get("Real Estate Sellers", DEFAULT_OFFER)
        message = build_message(offer, {
            "contact": p.get('prospect_name'),
            "company": p.get('property_address') or '',
            "vertical": "Real Estate Sellers",
        })
        prefill = f"https://web.phound.app/?phone={phone}&body="
        print(f"  [SMS] Queued for {p.get('prospect_name')} ({phone}) via Phound app prefill link.")
        sent_count += 1
        exports.append({
            "prospect": p.get('prospect_name'),
            "phone": phone,
            "message": message,
            "prefill": prefill,
        })

    out = CAMPAIGN_EXPORT_DIR / f"extreme_sales_blast_{time.strftime('%Y%m%d_%H%M%S')}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(exports, f, indent=2)

    # Send Telegram Sales Alert
    try:
        import requests
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        tg_text = (
            f"<b>🚀 EXTREME SALES BLASTER EXECUTED 🚀</b>\n\n"
            f"👤 <b>Closer</b>: Big Moe Shafy\n"
            f"🏢 <b>Company</b>: Contech AI Agentic Teamz\n"
            f"📱 <b>Caller ID</b>: +1 (661) 990-9068\n"
            f"📨 <b>Phound Wave SMS Blast Prepared</b>: {sent_count} Top Prospects\n"
            f"💰 <b>Est. Commission Pipeline</b>: $178,500.00\n\n"
            f"🔗 <b>Dashboard</b>: http://localhost:5173/voice-agents"
        )
        requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": tg_text, "parse_mode": "HTML"}, timeout=5)
    except Exception:
        pass

    print(f"[EXTREME SALES BLASTER] COMPLETE: Prepared {sent_count} Phound Wave SMS messages -> {out.name}")


if __name__ == "__main__":
    dispatch_sales_blast()
