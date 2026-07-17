import os
import json
import csv
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import glob

MBM_ROOT = r"C:\Users\omare\OneDrive\Desktop\AI\MBM"
PAINPOINTS_DIR = os.path.join(MBM_ROOT, "PainPoints")
ARTIFACTS_DIR = os.path.join(MBM_ROOT, "Artifacts")
TRACKING_FILE = os.path.join(ARTIFACTS_DIR, "sales_tracking.csv")

# Gmail SMTP Configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "abdelshafyclapps@gmail.com"
EMAIL_PASSWORD = "ffcd pjvx cmdf zbxg"

TODAY = datetime.now().strftime('%Y-%m-%d')

def init_tracking_file():
    if not os.path.exists(TRACKING_FILE):
        with open(TRACKING_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['Date', 'Business', 'Contact', 'Email', 'Pain_Type', 'Solution_Pitched', 'Potential_Value', 'Status'])

def send_pitch_email(business, contact, to_email, pain, solution, value):
    subject = f"Quick question about scaling {business}"
    
    body = f"""Hi {contact or 'Team'},

I noticed that {business} is currently {pain}. 

I run an AI automation agency and we specialize in exactly this - implementing {solution} to remove bottlenecks and empower your workforce. 
Based on what I've seen, deploying these specific automated jobs and app implementations will allow you to quickly review tasks, significantly decrease time spent on manual work, and drastically increase your overall accuracy.

This ultimately translates to {value} in direct value by saving time and directly increasing your profit margins.

I've put together a brief outline of how this would work for your specific setup. Are you open to a quick 5-minute chat this week to see if it makes sense?

Best,
Mohammed Abdelshafy
+201040404118
abdelshafyclapps@gmail.com
"""

    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"[FAIL] Error sending to {to_email}: {e}")
        return False

def run_sales_pipeline():
    init_tracking_file()
    
    # Get latest pain points file
    files = sorted(glob.glob(os.path.join(PAINPOINTS_DIR, "PAINPOINTS_*.json")), reverse=True)
    if not files:
        print("No pain points file found.")
        return
        
    latest_file = files[0]
    with open(latest_file, 'r') as f:
        pain_points = json.load(f)
        
    print(f"Loaded {len(pain_points)} pain points from {os.path.basename(latest_file)}")
    
    # Read already contacted
    contacted = set()
    with open(TRACKING_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            contacted.add(row['Email'].lower())
            
    new_pitches = 0
    with open(TRACKING_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        
        for pp in pain_points:
            email = pp.get('contact', '').strip()
            if not email or '@' not in email or email.lower() in contacted:
                continue
                
            business = pp.get('business', 'your business')
            pain = pp.get('pain', 'experiencing operational bottlenecks').lower()
            solution = pp.get('solution', 'AI automation')
            value = pp.get('potential_deal', 'significant savings')
            
            print(f"Sending pitch to {business} ({email})...")
            success = send_pitch_email(business, "", email, pain, solution, value)
            
            status = 'Sent' if success else 'Failed'
            writer.writerow([TODAY, business, "", email, pp.get('type', ''), solution, value, status])
            
            if success:
                new_pitches += 1
                
    print(f"\nPipeline complete. Sent {new_pitches} new pitches.")

if __name__ == "__main__":
    run_sales_pipeline()
