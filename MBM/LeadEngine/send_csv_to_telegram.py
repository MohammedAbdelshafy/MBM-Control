import os
import requests
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.resolve()
WORKSPACE_ROOT = BASE_DIR.parent.parent.resolve()

load_dotenv(WORKSPACE_ROOT / ".env")

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "").strip()

if not BOT_TOKEN or not CHAT_ID:
    print("Error: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing in .env")
    exit(1)

csv_files = [
    (WORKSPACE_ROOT / "real_estate_200_deals_top_prospects.csv", "🏠 Top 200 Real Estate Deals & Motivated Sellers (To Call Today)"),
    (WORKSPACE_ROOT / "top_200_prospects_to_call_today.csv", "📞 Top 200 Verified Prospects (To Call Today)")
]

url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"

for file_path, caption in csv_files:
    if file_path.exists():
        print(f"[TELEGRAM SENDER] Sending {file_path.name} to Telegram chat {CHAT_ID}...")
        with open(file_path, "rb") as f:
            resp = requests.post(
                url,
                data={"chat_id": CHAT_ID, "caption": caption},
                files={"document": (file_path.name, f, "text/csv")}
            )
        if resp.status_code == 200:
            print(f"[+] SUCCESS: Sent {file_path.name} to Telegram!")
        else:
            print(f"[-] Telegram API Error ({resp.status_code}): {resp.text}")
    else:
        print(f"[-] File not found: {file_path}")
