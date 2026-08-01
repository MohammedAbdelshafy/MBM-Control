import os
import json
import time
import smtplib
from email.message import EmailMessage
from dotenv import load_dotenv

class InvestorOutreach:
    def __init__(self):
        load_dotenv()
        # Ensure you set these in your GodMode/.env or MBM/.env
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = os.getenv("MASTER_GMAIL", "abdelshafyclapps@gmail.com")
        self.sender_password = os.getenv("GMAIL_APP_PASSWORD", "your-app-password") # Requires Gmail App Password
        
        self.log_file = os.path.join(os.path.dirname(__file__), "outreach_log.json")
        self.contacted_properties = self._load_log()
        
    def _load_log(self):
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r') as f:
                    return set(json.load(f))
            except:
                pass
        return set()
        
    def _save_log(self):
        with open(self.log_file, 'w') as f:
            json.dump(list(self.contacted_properties), f)

    def draft_offer_email(self, lead):
        address = lead.get('address', 'the property')
        agent = lead.get('agent', 'there')
        price = lead.get('price', 'your listing price')
        description = lead.get('description', '')
        
        gemini_key = os.getenv("GEMINI_API_KEY")
        if gemini_key and not gemini_key.startswith("your_"):
            try:
                import requests
                url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent"
                headers = {'Content-Type': 'application/json', 'X-goog-api-key': gemini_key}
                prompt = f"Write a professional, compelling, short cash offer email to real estate agent/seller '{agent}' for property at '{address}' listed at '{price}'. Highlight that we are cash buyers ready to close fast, asking for a 10-minute Google Meet call this week. Do not use placeholders."
                payload = {"contents": [{"parts": [{"text": prompt}]}]}
                res = requests.post(url, headers=headers, json=payload, timeout=10)
                if res.status_code == 200:
                    ai_text = res.json()['candidates'][0]['content']['parts'][0]['text']
                    subject = f"Cash Offer & Google Meet Request - {address}"
                    return subject, ai_text
            except Exception as e:
                print(f"AI Offer Drafting fallback: {e}")

        subject = f"Property Enquiry & Cash Offer - {address}"
        body = f"""Hi {agent},

We are an investment group acquiring residential assets in your market. We reviewed your listing for {address} ({price}) and want to discuss submitting a firm cash offer.

We are cash buyers with proof of funds ready to move quickly.

Do you have 10 minutes for a brief Google Meet video call this week to discuss terms and see if we can get a deal structured?

Best regards,
The Investment Acquisitions Team"""
        return subject, body

    def send_email(self, to_email, subject, body, dry_run=True):
        if dry_run:
            print(f"\n[DRY RUN] Would send to: {to_email}")
            print(f"Subject: {subject}")
            print(f"Body:\n{body}")
            print("-" * 40)
            return True
            
        try:
            msg = EmailMessage()
            msg.set_content(body)
            clean_subject = str(subject).replace('\n', ' ').replace('\r', ' ').strip()
            clean_to = str(to_email).replace('\n', '').replace('\r', '').strip()
            clean_from = str(self.sender_email).replace('\n', '').replace('\r', '').strip()
            msg['Subject'] = clean_subject
            msg['From'] = clean_from
            msg['To'] = clean_to

            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.send_message(msg)
            server.quit()
            
            print(f"Successfully sent offer for {to_email}")
            return True
        except Exception as e:
            print(f"Failed to send email to {to_email}: {e}")
            return False

    def execute_campaign(self, leads_file, dry_run=True):
        if not os.path.exists(leads_file):
            print(f"No leads file found at {leads_file}")
            return
            
        with open(leads_file, 'r', encoding='utf-8') as f:
            leads = json.load(f)
            
        print(f"Starting outreach for {len(leads)} leads. Dry run: {dry_run}")
        
        sent_count = 0
        try:
            from contact_enrichment import ContactEnricher
        except ImportError:
            from MBM.LeadEngine.contact_enrichment import ContactEnricher
        enricher = ContactEnricher()
        
        for lead in leads:
            prop_id = lead.get('id')
            if prop_id in self.contacted_properties:
                print(f"Skipping {prop_id} - already contacted.")
                continue
                
            # Find email & contact data
            agent = lead.get('agent', 'Real Estate Agent')
            city = lead.get('address', '').split(',')[-1].strip()
            
            contact_info = enricher.search_agency_email(agent, city)
            email = contact_info.get('email') if isinstance(contact_info, dict) else contact_info
            phone = contact_info.get('phone') if isinstance(contact_info, dict) else None
            
            if phone:
                print(f"Verified Phone Number for {agent}: {phone} (Available for SMS/Call)")
            
            if email:
                subject, body = self.draft_offer_email(lead)
                success = self.send_email(email, subject, body, dry_run)
                
                if success and not dry_run:
                    self.contacted_properties.add(prop_id)
                    self._save_log()
                    sent_count += 1
                    time.sleep(10) # Delay between emails to avoid spam filters
            else:
                print(f"No email found for {agent}. Skipping.")
                
        print(f"Outreach complete. Sent {sent_count} new emails.")

if __name__ == "__main__":
    outreach = InvestorOutreach()
    leads_file = os.path.join(os.path.dirname(__file__), "leads_manchester.json")
    outreach.execute_campaign(leads_file, dry_run=True)
