import os
import sys
import json
import time
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from dotenv import load_dotenv

# Add parent dir
sys.path.append(os.path.dirname(__file__))
from contact_enrichment import ContactEnricher

load_dotenv()

LOGS_DIR = os.path.join(os.path.dirname(__file__), 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)
CADENCE_LOG = os.path.join(LOGS_DIR, 'cadence_history.json')

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_line = f"[CADENCE ENGINE] {timestamp} - {msg}"
    print(log_line)

class MultiTouchCadenceEngine:
    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = os.getenv("MASTER_GMAIL", "abdelshafyclapps@gmail.com")
        self.sender_password = os.getenv("GMAIL_APP_PASSWORD", "kmmskgfswwhfsssl")
        self.gemini_key = os.getenv("GEMINI_API_KEY")
        self.history = self._load_history()

    def _load_history(self):
        if os.path.exists(CADENCE_LOG):
            try:
                with open(CADENCE_LOG, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    def _save_history(self):
        with open(CADENCE_LOG, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, indent=2)

    def generate_ai_followup(self, agent, address, touch_number):
        if self.gemini_key and not self.gemini_key.startswith("your_"):
            try:
                import requests
                url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
                headers = {'Content-Type': 'application/json', 'X-goog-api-key': self.gemini_key}
                
                if touch_number == 2:
                    prompt = f"Write a quick, polite 3-sentence follow-up email to real estate agent/seller '{agent}' about property '{address}'. Remind them of our cash offer, highlight zero fees and 7-day closing, and ask for a 10-minute Google Meet call. No placeholders."
                elif touch_number == 3:
                    prompt = f"Write a compelling follow-up email offering a free proof of funds / quick video call for property '{address}' to '{agent}'. High urgency, professional, cash buyers. No placeholders."
                else:
                    prompt = f"Write a short, polite 'breakup' email to '{agent}' regarding property '{address}'. Mention we are wrapping up our acquisitions for this zone this week, asking one last time for a brief Google Meet call before withdrawing our offer. No placeholders."

                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                res = requests.post(url, headers=headers, json=payload, timeout=10)
                if res.status_code == 200:
                    ai_text = res.json()['candidates'][0]['content']['parts'][0]['text']
                    subject = f"Re: Cash Offer & Google Meet Request - {address}" if touch_number < 4 else f"Final Notice: Acquisition Offer - {address}"
                    return subject, ai_text
            except Exception as e:
                log(f"AI Followup Generation fallback: {e}")

        # Static High-Converting Fallback Templates
        if touch_number == 2:
            subject = f"Re: Cash Offer - {address}"
            body = f"""Hi {agent},

Following up on our cash offer for {address}. 

We are actively deploying capital in your area and can complete contracts within 7–10 days with zero buyer commissions or fees.

Do you have 10 minutes for a brief Google Meet call this week to review terms?

Best regards,
Acquisitions Team"""
        elif touch_number == 3:
            subject = f"Proof of Funds & Fast Close - {address}"
            body = f"""Hi {agent},

Just checking in regarding {address}. We have cash reserves allocated for quick completion this month.

If the seller is motivated for a clean, hassle-free transaction, we are prepared to submit a formal contract today.

Would tomorrow or Thursday work for a 10-minute Google Meet video call?

Best regards,
Acquisitions Team"""
        else:
            subject = f"Closing File / Final Follow-up - {address}"
            body = f"""Hi {agent},

We are finalizing our property acquisitions for this quarter and wanted to touch base one last time regarding {address}.

If this property is still available and the seller wishes to entertain a firm cash offer, please let us know by end of day tomorrow.

Best regards,
Acquisitions Team"""

        return subject, body

    def send_email(self, to_email, subject, body):
        if not self.sender_password or self.sender_password == "your-app-password":
            log(f"Skipping email to {to_email}: Missing GMAIL_APP_PASSWORD")
            return False

        clean_subject = str(subject).replace('\n', ' ').replace('\r', ' ').strip()
        clean_to = str(to_email).replace('\n', '').replace('\r', '').strip()
        clean_from = f"Investment Acquisitions <{self.sender_email.strip()}>"

        msg = EmailMessage()
        msg['Subject'] = clean_subject
        msg['From'] = clean_from
        msg['To'] = clean_to
        msg.set_content(body)

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            log(f"✅ Follow-up email sent successfully to {to_email}")
            return True
        except Exception as e:
            log(f"❌ Failed to send follow-up to {to_email}: {e}")
            return False

    def process_cadence(self, leads_file):
        if not os.path.exists(leads_file):
            log("No leads file found for cadence execution.")
            return

        with open(leads_file, 'r', encoding='utf-8') as f:
            leads = json.load(f)

        log(f"Running Multi-Touch Cadence for {len(leads)} leads...")
        now = datetime.now()

        for lead in leads:
            prop_id = str(lead.get('id'))
            email = lead.get('agent_email')
            agent = lead.get('agent', 'Property Manager')
            address = lead.get('address', 'the property')

            if not email or '@' not in email:
                continue

            record = self.history.get(prop_id, {
                "touches": 0,
                "last_touch": None,
                "email": email,
                "agent": agent,
                "address": address
            })

            touches = record.get("touches", 0)
            last_touch_str = record.get("last_touch")

            # Check if due for next touch
            should_send = False
            next_touch_num = touches + 1

            if touches == 0:
                # Touch 1 was handled by initial outreach, mark as 1
                record["touches"] = 1
                record["last_touch"] = now.strftime('%Y-%m-%d %H:%M:%S')
                self.history[prop_id] = record
                continue
            elif last_touch_str:
                last_dt = datetime.strptime(last_touch_str, '%Y-%m-%d %H:%M:%S')
                days_since = (now - last_dt).total_seconds() / 86400.0
                
                # Touch 2: 2 days after Touch 1
                # Touch 3: 4 days after Touch 2
                # Touch 4: 5 days after Touch 3
                if touches == 1 and days_since >= 2.0:
                    should_send = True
                elif touches == 2 and days_since >= 3.0:
                    should_send = True
                elif touches == 3 and days_since >= 4.0:
                    should_send = True

            if should_send and next_touch_num <= 4:
                log(f"Executing Touch #{next_touch_num} for {agent} ({email}) on {address}...")
                subject, body = self.generate_ai_followup(agent, address, next_touch_num)
                success = self.send_email(email, subject, body)
                
                if success:
                    record["touches"] = next_touch_num
                    record["last_touch"] = now.strftime('%Y-%m-%d %H:%M:%S')
                    self.history[prop_id] = record
                    self._save_history()
                    time.sleep(10) # Anti-spam delay

        self._save_history()
        log("Multi-Touch Cadence Cycle Complete.")

if __name__ == "__main__":
    base_dir = os.path.dirname(__file__)
    engine = MultiTouchCadenceEngine()
    engine.process_cadence(os.path.join(base_dir, 'enriched_global_leads.json'))
