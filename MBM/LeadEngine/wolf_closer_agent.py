import os
import sys
import json
import time
import imaplib
import email
import smtplib
from email.header import decode_header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import requests
from dotenv import load_dotenv

# Ensure we can import MBM modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "Scripts"))

try:
    from telegram_notify import send_message
except ImportError:
    def send_message(msg):
        print(f"[TELEGRAM FALLBACK] {msg}")

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env'))

GMAIL_USER = os.getenv("MASTER_GMAIL", "abdelshafyclapps@gmail.com")
GMAIL_PASS = os.getenv("GMAIL_APP_PASSWORD")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

system_instruction = """You are the ultimate 'Wolf of Wall Street' Closing Agent.
Your objective is to close deals, handle objections with extreme prejudice, and push the prospect relentlessly towards booking a call or signing up. 
You are authoritative, confident, persuasive, and completely unfazed by rejection. You never take 'no' for an answer without a fight.

When given an email thread from a prospect:
1. Determine if HUMAN INTERVENTION is required right now. Human intervention is ONLY required if:
   - They ask for a contract / "Where do I sign?"
   - They want payment details / "How do I pay?"
   - They are asking a highly technical operational question you cannot bluff through.
   - They explicitly demand a human or a phone call immediately.

2. If human intervention IS required, set "requires_human" to true.
3. If human intervention IS NOT required, write a relentless, short, punchy, persuasive reply pushing them to the next step (booking a meeting or saying 'let's do this'). Use urgency. Use FOMO (Fear Of Missing Out). Do not be overly polite or weak. Be a shark.

OUTPUT FORMAT MUST BE STRICTLY JSON:
{
    "requires_human": true or false,
    "reason": "Brief reason why human is/isn't needed",
    "reply_body": "The exact email text to send back to them. Leave empty if requires_human is true."
}
"""

def call_gemini(user_prompt):
    if not GEMINI_API_KEY:
        return None
    
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={GEMINI_API_KEY}"
    payload = {
        "system_instruction": {"parts": [{"text": system_instruction}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "response_mime_type": "application/json"
        }
    }
    
    try:
        res = requests.post(url, json=payload, timeout=30)
        res.raise_for_status()
        return json.loads(res.json()["candidates"][0]["content"]["parts"][0]["text"])
    except Exception as e:
        print(f"[WOLF CLOSER] Gemini Error: {e}")
        return None

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

def send_auto_reply(to_email, subject, body):
    if not subject.startswith("Re:"):
        subject = "Re: " + subject
        
    msg = MIMEMultipart()
    msg['From'] = GMAIL_USER
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASS)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"[WOLF CLOSER] SMTP Send Error: {e}")
        return False

def check_and_close_emails():
    print("[WOLF CLOSER] Prowling the inbox for unread leads...")
    if not GMAIL_USER or not GMAIL_PASS:
        print("[WOLF CLOSER] Missing credentials.")
        return

    try:
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(GMAIL_USER, GMAIL_PASS)
        mail.select("inbox")
        
        status, messages = mail.search(None, "UNSEEN")
        if not messages[0]:
            mail.logout()
            return
            
        email_ids = messages[0].split()
        
        for e_id in email_ids:
            # Peek first to check subject without marking seen
            status, msg_data = mail.fetch(e_id, "(BODY.PEEK[HEADER.FIELDS (SUBJECT)])")
            subject = "Unknown"
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    sub, encoding = decode_header(msg.get("Subject", ""))[0]
                    if isinstance(sub, bytes):
                        subject = sub.decode(encoding if encoding else "utf-8")
                        
            lower_subject = subject.lower()
            if "undelivered" in lower_subject or "delivery status notification" in lower_subject or "mailer-daemon" in lower_subject:
                # Leave for ai_ops_agent
                continue
                
            # Filter: Only process actual replies (not newsletters, marketing, etc.)
            status, peek_msg_data = mail.fetch(e_id, "(BODY.PEEK[HEADER.FIELDS (IN-REPLY-TO)])")
            in_reply_to = ""
            for response_part in peek_msg_data:
                if isinstance(response_part, tuple):
                    peek_msg = email.message_from_bytes(response_part[1])
                    in_reply_to = peek_msg.get("In-Reply-To", "")
            
            is_reply = bool(in_reply_to) or lower_subject.startswith("re:") or lower_subject.startswith("re :")
            if not is_reply:
                print(f"[WOLF CLOSER] Ignoring non-reply email: {subject}")
                continue
                
            # Fetch full email (marks as SEEN)
            status, msg_data = mail.fetch(e_id, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    sub, encoding = decode_header(msg.get("Subject", ""))[0]
                    if isinstance(sub, bytes):
                        subject = sub.decode(encoding if encoding else "utf-8")
                        
                    sender = msg.get("From")
                    body = get_email_body(msg)
                    
                    print(f"[WOLF CLOSER] Found prey: Email from {sender}")
                    
                    # Feed to Gemini
                    prompt = f"Email from Prospect:\nFrom: {sender}\nSubject: {subject}\nMessage:\n{body}\n\nAssess and generate response JSON."
                    ai_response = call_gemini(prompt)
                    
                    if not ai_response:
                        continue
                        
                    if ai_response.get("requires_human", False):
                        print(f"[WOLF CLOSER] ALERT: Human needed for {sender}")
                        tg_msg = f"🚨 *WOLF CLOSER ALERT: HOT LEAD* 🚨\n*Prospect:* {sender}\n*Subject:* {subject}\n\n*Why I need you:* {ai_response.get('reason')}\n\n*Client Msg:*\n{body[:500]}\n\nGet in there and close it!"
                        send_message(tg_msg)
                    else:
                        reply_text = ai_response.get("reply_body", "")
                        print(f"[WOLF CLOSER] Pushing for the close with {sender}...")
                        success = send_auto_reply(sender, subject, reply_text)
                        if success:
                            tg_msg = f"🐺 *WOLF CLOSER AUTO-REPLIED* 🐺\n*Prospect:* {sender}\n*Subject:* {subject}\n\n*My Rebuttal:*\n{reply_text}"
                            send_message(tg_msg)
                        
        mail.logout()
    except Exception as e:
        print(f"[WOLF CLOSER] IMAP Error: {e}")

def run_daemon():
    print("========================================")
    print("🐺 THE WOLF CLOSER AGENT IS ONLINE 🐺")
    print("========================================")
    while True:
        check_and_close_emails()
        time.sleep(300) # Check every 5 minutes

if __name__ == "__main__":
    once = "--once" in sys.argv
    if once:
        check_and_close_emails()
    else:
        run_daemon()
