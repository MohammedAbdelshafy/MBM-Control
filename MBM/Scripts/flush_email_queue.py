import json
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path

QUEUE_FILE = Path(r"C:\Users\omare\OneDrive\Desktop\AI\MBM\Logs\email_queue.json")

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = os.environ.get("SMTP_USER", "abdelshafyclapps@gmail.com")
EMAIL_PASSWORD = os.environ.get("SMTP_PASS", "")

def send_email(to_email, subject, body, attachment_path=None):
    if not EMAIL_PASSWORD:
        print("[FAIL] Missing SMTP_PASS environment variable.")
        return False
        
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = to_email
    msg['Subject'] = subject
    
    msg.attach(MIMEText(body, 'plain'))
    
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

def flush_queue():
    if not QUEUE_FILE.exists():
        print("No email queue found.")
        return
        
    with open(QUEUE_FILE, 'r') as f:
        try:
            queue = json.load(f)
        except json.JSONDecodeError:
            print("Queue file is empty or corrupted.")
            return

    processed = 0
    for item in queue:
        if item.get("status") == "queued":
            print(f"Processing queued email to {item.get('to')}...")
            success = send_email(
                item.get("to"),
                item.get("subject"),
                item.get("body"),
                item.get("attachment")
            )
            if success:
                item["status"] = "SENT_DISPATCHED"
                processed += 1
                
    with open(QUEUE_FILE, 'w') as f:
        json.dump(queue, f, indent=2)
        
    print(f"Processed {processed} emails from queue.")

if __name__ == "__main__":
    flush_queue()
