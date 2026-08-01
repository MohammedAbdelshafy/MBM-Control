import os
import csv
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# Load credentials from .env (in a real setup, load dotenv)
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

PITCH_TEMPLATE = """
Hi {name},

I noticed that {business_name} might be missing out on after-hours calls or dealing with busy front-desk staff. 

I build AI Voice Receptionists for {niche}s that handle calls 24/7, answer FAQs, and even book appointments directly onto your calendar. It sounds exactly like a real human.

You can actually call my live demo number right now to test it yourself: (555) 123-4567.

If you like what you hear, I'd love to build one customized for {business_name}. We charge a one-time setup fee of $2,000 and $199/month. 

Let me know if you'd like to see a custom demo!

Best,
Your Name
AI Agency Director
"""

def send_email(to_email, subject, body):
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        print(f"[Simulation] Would send email to {to_email} with subject: {subject}")
        return True
        
    msg = MIMEMultipart()
    msg['From'] = SMTP_USERNAME
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        print(f"Sent email to {to_email}")
        return True
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")
        return False

def run_blaster(csv_path):
    print("Starting Cold Email Blaster...")
    
    if not os.path.exists(csv_path):
        print(f"Error: {csv_path} not found.")
        return
        
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            business_name = row.get("name", "your business")
            email = row.get("email")
            niche = row.get("niche", "business")
            
            # Simple personalization
            contact_name = "Team"
            
            body = PITCH_TEMPLATE.format(
                name=contact_name,
                business_name=business_name,
                niche=niche
            )
            
            subject = f"AI Receptionist for {business_name}"
            send_email(email, subject, body)
            
    print("Campaign finished!")

if __name__ == "__main__":
    csv_file = os.path.join(os.path.dirname(__file__), "..", "..", "b2b_sales", "leads_database.csv")
    run_blaster(csv_file)
