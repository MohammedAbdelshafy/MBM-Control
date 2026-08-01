"""
Client Answer & Reply Checker Agent
======================================
Mission: Scans Gmail IMAP inbox specifically for human client/lead responses to sent emails,
extracts the buyer's reply content, and alerts Telegram immediately with a HOT LEAD summary.
"""

import os
import sys
import json
import imaplib
import email
from email.header import decode_header
import requests
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.resolve()
LOGS_DIR = BASE_DIR / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)
REPLIES_FILE = LOGS_DIR / 'checked_replies.json'

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

GMAIL_USER = os.getenv("MASTER_GMAIL", "abdelshafyclapps@gmail.com")
GMAIL_PASS = os.getenv("GMAIL_APP_PASSWORD", "enahvqoshdtnayib")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "TELEGRAM_BOT_TOKEN_REDACTED")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "6617518949")


def send_telegram_alert(text):
    if TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        try:
            requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "Markdown"}, timeout=10)
        except Exception as e:
            print(f"Telegram notice: {e}")


def get_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            ct = part.get_content_type()
            if ct == "text/plain":
                try:
                    return part.get_payload(decode=True).decode(errors="replace")
                except Exception:
                    pass
    else:
        try:
            return msg.get_payload(decode=True).decode(errors="replace")
        except Exception:
            pass
    return ""


def check_if_anyone_answered():
    print("============================================================")
    print("[ANSWER CHECKER AGENT] SCANNING FOR CLIENT REPLIES & ANSWERS")
    print("============================================================")

    answered_clients = []

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_PASS)
        mail.select("inbox")

        # Search for unseen messages
        status, data = mail.search(None, "UNSEEN")
        e_ids = data[0].split()

        print(f"[ANSWER CHECKER] Found {len(e_ids)} unread messages in inbox.")

        for e_id in e_ids:
            status, msg_data = mail.fetch(e_id, "(RFC822)")
            for part in msg_data:
                if isinstance(part, tuple):
                    msg = email.message_from_bytes(part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8", errors="replace")
                    
                    sender = msg.get("From", "Unknown Sender")
                    body = get_body(msg)
                    lower_subj = str(subject).lower()

                    # Ignore automated bounces and marketing
                    if "undelivered" in lower_subj or "mailer-daemon" in str(sender).lower() or "twitter" in str(sender).lower():
                        continue

                    # Direct lead answer condition (Re: or In-Reply-To)
                    in_reply = msg.get("In-Reply-To")
                    if bool(in_reply) or lower_subj.startswith("re:") or lower_subj.startswith("re :"):
                        sender_clean = str(sender).encode("ascii", errors="replace").decode("ascii")
                        subj_clean = str(subject).encode("ascii", errors="replace").decode("ascii")
                        snippet = body[:250].replace('\n', ' ')

                        record = {
                            "sender": sender_clean,
                            "subject": subj_clean,
                            "snippet": snippet,
                            "timestamp": datetime.now().isoformat()
                        }
                        answered_clients.append(record)

                        print(f"  🔥 HOT LEAD REPLIED: {sender_clean} | Subj: {subj_clean}")

                        # Push alert to Telegram
                        alert_msg = (
                            f"🚨 *NEW CLIENT ANSWER RECEIVED!*\n\n"
                            f"👤 *From*: `{sender_clean}`\n"
                            f"📌 *Subject*: `{subj_clean}`\n"
                            f"💬 *Preview*: {snippet}\n\n"
                            f"⚡ *Wolf Closer Agent handling response.*"
                        )
                        send_telegram_alert(alert_msg)

        mail.logout()
    except Exception as e:
        err_clean = str(e).encode("ascii", errors="replace").decode("ascii")
        print(f"[ANSWER CHECKER] IMAP Notice: {err_clean}")

    with open(REPLIES_FILE, "w", encoding="utf-8") as f:
        json.dump(answered_clients, f, indent=2)

    print(f"\n[COMPLETE] Answer Checker Finished ({len(answered_clients)} Human Replies Found).")
    return answered_clients


if __name__ == "__main__":
    check_if_anyone_answered()
