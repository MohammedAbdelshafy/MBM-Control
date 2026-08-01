import os
import sys
import json
import time
import glob
import re
import imaplib
import email
from email.header import decode_header
import requests
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv

# Ensure we can import MBM modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "LeadEngine"))

from telegram_notify import send_message
from contact_enrichment import ContactEnricher

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

GMAIL_USER = os.getenv("MASTER_GMAIL", "abdelshafyclapps@gmail.com")
GMAIL_PASS = os.getenv("GMAIL_APP_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def call_gemini(system_prompt, user_prompt):
    if not GEMINI_API_KEY:
        return "Error: GEMINI_API_KEY not found."
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
    }
    
    try:
        res = requests.post(url, json=payload, timeout=30)
        res.raise_for_status()
        return res.json()["candidates"][0]["content"]["parts"][0]["text"]
    except Exception as e:
        return f"AI Generation Error: {str(e)}"

# Fixed system prompt reference
system_instruction = "You are the MBM AI Ops & Support Agent."

def inspect_failed_runs():
    print("[AI OPS] Inspecting failed runs in Logs...")
    logs_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "Logs")
    if not os.path.exists(logs_dir):
        return
        
    cutoff_time = time.time() - 3600  # Only check logs from the last hour
    recent_logs = []
    
    for log_file in glob.glob(os.path.join(logs_dir, "*.log")):
        if os.path.getmtime(log_file) >= cutoff_time:
            recent_logs.append(log_file)
            
    for log_file in recent_logs:
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                content = f.read()
                if "Traceback" in content or "Exception" in content or "Failed" in content:
                    print(f"[AI OPS] Error detected in {os.path.basename(log_file)}")
                    # Grab last 2000 chars of the log
                    snippet = content[-2000:]
                    prompt = f"Analyze this error log snippet and provide a brief Root Cause Analysis and a suggested fix:\n\n{snippet}"
                    
                    analysis = call_gemini(system_instruction, prompt)
                    
                    msg = f"⚠️ *FAILED RUN DETECTED*\n*Log:* `{os.path.basename(log_file)}`\n\n*AI Analysis:*\n{analysis}"
                    send_message(msg)
        except Exception as e:
            print(f"[AI OPS] Could not read log {log_file}: {e}")

def get_email_body(msg):
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            try:
                body = part.get_payload(decode=True).decode()
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    return body
            except:
                pass
    else:
        try:
            return msg.get_payload(decode=True).decode()
        except:
            pass
    return ""

def process_undelivered_email(subject, body):
    print("[AI OPS] Processing undelivered email bounce...")
    # Extract the bounced email address
    match = re.search(r'([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', body)
    bounced_email = match.group(1) if match else "Unknown"
    
    if bounced_email == "Unknown":
        send_message(f"📬 *Bounce Detected*\nCould not extract bounced email address.")
        return

    # Extract potential domain/company name to search
    domain = bounced_email.split("@")[-1] if "@" in bounced_email else bounced_email
    company_name = domain.split(".")[0].capitalize()
    
    send_message(f"📬 *Bounce Detected*\nEmail to `{bounced_email}` failed. Triggering search for new contact details for `{company_name}`...")
    
    # Try to find new contact details
    enricher = ContactEnricher()
    # Using generic search for the domain/company
    new_emails, phone = enricher.search_agency_email(company_name, "")
    
    if new_emails or phone:
        msg = f"✅ *New Contact Found for {company_name}*\n"
        if new_emails:
            msg += f"New Emails: {', '.join(new_emails)}\n"
        if phone:
            msg += f"New Phone: {phone}\n"
        msg += f"\n(Original bounced: {bounced_email})"
        send_message(msg)
    else:
        send_message(f"❌ *New Contact Search Failed*\nCould not find new details for {company_name} (Bounced: {bounced_email})")

def process_client_reply(sender, subject, body):
    print(f"[AI OPS] Processing client reply from {sender}...")
    prompt = f"We received an email from a client.\nSender: {sender}\nSubject: {subject}\nBody:\n{body}\n\nPlease draft a professional, polite response. If it's a complaint, be empathetic. If it's a sales inquiry, be helpful and push for a quick meeting."
    draft = call_gemini(system_instruction, prompt)
    
    msg = f"✉️ *New Client Reply*\n*From:* {sender}\n*Subject:* {subject}\n\n*AI Drafted Response:*\n{draft}\n\n*(Send this manually via Gmail or reply in thread)*"
    send_message(msg)

def check_emails():
    print("[AI OPS] Checking Gmail for unread emails...")
    if not GMAIL_USER or not GMAIL_PASS:
        print("[AI OPS] Missing Gmail credentials.")
        return

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_PASS)
        mail.select("inbox")
        
        status, messages = mail.search(None, "UNSEEN")
        email_ids = messages[0].split()
        
        for e_id in email_ids:
            status, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                    
                    sender = msg.get("From")
                    body = get_email_body(msg)
                    
                    lower_subject = subject.lower()
                    
                    # Process bounces
                    if "undelivered" in lower_subject or "delivery status notification" in lower_subject or "mailer-daemon" in sender.lower():
                        process_undelivered_email(subject, body)
                        continue
                        
                    # Filter: Only process actual replies (not newsletters, marketing, etc.)
                    in_reply_to = msg.get("In-Reply-To")
                    is_reply = bool(in_reply_to) or lower_subject.startswith("re:") or lower_subject.startswith("re :")
                    
                    if not is_reply:
                        sender_clean = str(sender).encode('ascii', errors='replace').decode('ascii')
                        subject_clean = str(subject).encode('ascii', errors='replace').decode('ascii')
                        print(f"[AI OPS] Ignoring non-reply email from {sender_clean}: {subject_clean}")
                        continue
                        
                    process_client_reply(sender, subject, body)
                        
        mail.logout()
    except Exception as e:
        err_clean = str(e).encode('ascii', errors='replace').decode('ascii')
        print(f"[AI OPS] IMAP Email Notice: {err_clean}")

def run_ops_agent():
    print("=== MBM AI OPS & SUPPORT AGENT ===")
    inspect_failed_runs()
    check_emails()
    print("=== OPS RUN COMPLETE ===")

if __name__ == "__main__":
    run_ops_agent()
