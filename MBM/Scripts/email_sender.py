"""
MBM Lead Pack - Email Sender
==============================
Automated email sending via Gmail SMTP.
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
import os

# Gmail SMTP Configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "abdelshafyclapps@gmail.com"
EMAIL_PASSWORD = "ffcd pjvx cmdf zbxg"

def send_email(to_email, subject, body, attachment_path=None):
    """Send an email with optional attachment."""
    
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'plain'))
    
    # Attach file if provided
    if attachment_path and os.path.exists(attachment_path):
        with open(attachment_path, 'rb') as f:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(f.read())
            encoders.encode_base64(part)
            filename = os.path.basename(attachment_path)
            part.add_header('Content-Disposition', f'attachment; filename={filename}')
            msg.attach(part)
    
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"[OK] Email sent to {to_email}")
        return True
    except Exception as e:
        print(f"[FAIL] Failed to send to {to_email}: {e}")
        return False

def send_packs():
    """Send lead packs to all targets."""
    
    # Email templates
    templates = {
        "piphouse": {
            "to": "PipHousellc@gmail.com",
            "subject": "Daily DFW Distressed Seller & Wholesaler Leads - Free Sample Attached",
            "body": """Hi PipHouse Team,

I run a lead generation service focused on the DFW real estate market. We pull fresh, daily leads from public records including:

- Dallas 311 code violations (distressed sellers)
- OpenStreetMap verified wholesalers
- RealEstateBees, HouseCashin, KeyCrew directories
- BiggerPockets active investors

What we deliver every morning by 9 AM CT:

1. Seller Leads (300-600/day): Property addresses, owner names, distress signals, confidence scores
2. Buyer/Wholesaler Leads (50-100/day): Company names, contacts, websites, verified sources

I'd love to send you a free sample pack so you can see the quality. No strings attached.

Pricing:
- Single pack (seller OR buyer): $25/day
- Full pack (both): $40/day
- Monthly subscription: $500/month (22 working days)

Are you open to a quick 5-minute call this week? I can walk you through the data and send over a sample.

Best,
Mohammed Abdelshafy
+201040404118
abdelshafyplay@gmail.com"""
        },
        "swift": {
            "to": "investments@swifthomesolutions.com",
            "subject": "Daily DFW Distressed Seller & Wholesaler Leads - Free Sample Attached",
            "body": """Hi Swift Home Solutions Team,

I run a lead generation service focused on the DFW real estate market. We pull fresh, daily leads from public records including:

- Dallas 311 code violations (distressed sellers)
- OpenStreetMap verified wholesalers
- RealEstateBees, HouseCashin, KeyCrew directories
- BiggerPockets active investors

What we deliver every morning by 9 AM CT:

1. Seller Leads (300-600/day): Property addresses, owner names, distress signals, confidence scores
2. Buyer/Wholesaler Leads (50-100/day): Company names, contacts, websites, verified sources

I'd love to send you a free sample pack so you can see the quality. No strings attached.

Pricing:
- Single pack (seller OR buyer): $25/day
- Full pack (both): $40/day
- Monthly subscription: $500/month (22 working days)

Are you open to a quick 5-minute call this week? I can walk you through the data and send over a sample.

Best,
Mohammed Abdelshafy
+201040404118
abdelshafyplay@gmail.com"""
        },
        "diamond": {
            "to": "diamondacquisitions@outlook.com",
            "subject": "Fresh DFW Wholesale Deals - Daily Leads from Public Records",
            "body": """Hi Diamond Acquisitions Team,

I noticed you're active in the DFW real estate space. I run a daily lead service that pulls fresh distressed seller and wholesaler leads from public records.

Today's sample:
- 375 distressed sellers (Dallas 311 code violations)
- 72 verified wholesalers and cash buyers
- Sources: Dallas Open Data API, KeyCrew, HouseCashin, RealEstateBees

I'd like to offer you a free week of leads to test the quality. No payment required - just reply with your email and I'll send the pack.

Pricing if you want to continue:
- $25/day for sellers OR buyers
- $40/day for both
- $500/month unlimited

Want me to send this week's pack?

Best,
Mohammed Abdelshafy
+201040404118
abdelshafyplay@gmail.com"""
        }
    }
    
    # Lead pack attachment
    pack_dir = r"C:\Users\omare\OneDrive\Desktop\AI\MBM\LeadPacks\Pack_2026-07-07"
    attachment = os.path.join(pack_dir, "FULL_PACK_2026-07-07.csv")
    
    print("="*60)
    print("MBM LEAD PACK - EMAIL CAMPAIGN")
    print("="*60)
    
    results = []
    for name, template in templates.items():
        print(f"\nSending to {template['to']}...")
        success = send_email(
            to_email=template['to'],
            subject=template['subject'],
            body=template['body'],
            attachment_path=attachment
        )
        results.append({"name": name, "success": success})
    
    print("\n" + "="*60)
    print("RESULTS")
    print("="*60)
    for r in results:
        status = "[OK] Sent" if r['success'] else "[FAIL] Failed"
        print(f"  {r['name']}: {status}")

if __name__ == "__main__":
    send_packs()
