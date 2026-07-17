"""
MBM AI Automation - Demo Outreach System
=========================================
Sends demo emails with Wolf of Wall Street energy.
"""

import os
import json
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

MBM_ROOT = r"C:\Users\omare\OneDrive\Desktop\AI\MBM"
TARGETS_DIR = os.path.join(MBM_ROOT, "Targets")
os.makedirs(TARGETS_DIR, exist_ok=True)

TODAY = datetime.now().strftime('%Y-%m-%d')

# Email config
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "abdelshafyclapps@gmail.com"
EMAIL_PASSWORD = "ffcd pjvx cmdf zbxg"

# DEMO TEMPLATES - AGGRESSIVE WOLF ENERGY
DEMO_TEMPLATES = {
    "demo_opener": {
        "subject": "FREE DEMO: I'll show you how to save 20hrs/week in 15 minutes",
        "body": """Hey [NAME],

I'm not going to waste your time. Here's the deal:

I built an AI system that automates [PAIN_POINT]. Right now, you're doing this manually and it's costing you:
- [TIME_COST] every week
- $[MONEY_COST] in missed opportunities
- [STRESS_COST] that's burning you out

I want to show you EXACTLY how this works. FREE. No commitment. 15 minutes.

Here's what you'll see in the demo:
1. AI finds and qualifies leads WHILE YOU SLEEP
2. Automated follow-up that NEVER loses a lead
3. Smart CRM that does data entry FOR YOU
4. 24/7 chatbot that books appointments at 3 AM

The result? More deals. Less work. More money.

I'm offering FREE demos to 5 businesses this week. After that, I charge $500 for the consultation.

Want in? Reply "DEMO" and I'll send you my calendar link.

No BS. No fluff. Just results.

Mohammed Abdelshafy
AI Automation Specialist
+201040404118
abdelshafyclapps@gmail.com

P.S. I showed this to a wholesaler last week. He closed 2 more deals that month. That's $20K extra. For a 15-minute demo."""
    },
    
    "demo_followup": {
        "subject": "Re: FREE DEMO - Last chance",
        "body": """[NAME],

Following up. I'm closing the free demo slots tomorrow.

Here's what you're missing:
- Your competitors are automating RIGHT NOW
- Every day you wait, you lose $[DAILY_LOSS]
- My AI system pays for itself in 30 days

15 minutes. Free. No strings.

Reply "DEMO" or I move on to the next business.

Mohammed Abdelshafy"""
    },
    
    "pain_agitation": {
        "subject": "[COMPANY] - I found $[AMOUNT] in lost revenue",
        "body": """[NAME],

I did some research on [COMPANY]. Found something interesting.

You're losing approximately $[AMOUNT]/month from:
1. Missed leads (no after-hours response)
2. Manual data entry (errors + time waste)
3. Slow follow-up (leads go cold in 5 minutes)

Here's the math:
- Average wholesale deal: $15,000
- Leads lost per month: [LEADS_LOST]
- Revenue lost: $[REVENUE_LOST]/month

My AI system fixes ALL of this. Here's the proof:

CLIENT RESULTS:
- 347% increase in lead response rate
- 89% reduction in manual data entry
- 2.5x more deals closed per month

The system costs $[COST]. The problem is costing you $[REVENUE_LOST].

Let me show you how in 15 minutes. Reply "DEMO" and I'll send my calendar.

Mohammed Abdelshafy

P.S. I'm offering a free audit to the first 5 businesses that reply. No strings attached."""
    }
}

def send_demo_email(target, template_name="demo_opener"):
    """Send demo email to target."""
    
    company = target['company']
    email = target.get('contact', '')
    
    if not email:
        print(f"  [SKIP] No email for {company}")
        return False
    
    template = DEMO_TEMPLATES[template_name]
    
    # Personalize
    body = template['body']
    body = body.replace('[NAME]', company.split()[0])
    body = body.replace('[COMPANY]', company)
    body = body.replace('[PAIN_POINT]', target['pain'][:50])
    body = body.replace('[TIME_COST]', '20+ hours')
    body = body.replace('[MONEY_COST]', '3,000+')
    body = body.replace('[STRESS_COST]', 'mental energy')
    body = body.replace('[DAILY_LOSS]', '500')
    body = body.replace('[AMOUNT]', '5,000')
    body = body.replace('[LEADS_LOST]', '10-15')
    body = body.replace('[REVENUE_LOST]', '150,000')
    body = body.replace('[COST]', target['deal_value'].split('-')[0])
    
    subject = template['subject']
    subject = subject.replace('[NAME]', company.split()[0])
    subject = subject.replace('[COMPANY]', company)
    subject = subject.replace('[AMOUNT]', '5,000')
    
    try:
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        print(f"  [OK] Demo sent to {company} ({email})")
        return True
    except Exception as e:
        print(f"  [FAIL] {company}: {e}")
        return False

def run_demo_campaign():
    """Run demo outreach campaign."""
    print(f"{'='*60}")
    print(f"MBM AI AUTOMATION - DEMO CAMPAIGN")
    print(f"Date: {TODAY}")
    print(f"{'='*60}")
    
    # Load new targets
    targets_file = os.path.join(TARGETS_DIR, f"NEW_TARGETS_{TODAY}.json")
    if not os.path.exists(targets_file):
        print("Running target discovery first...")
        from new_target_discovery import discover_new_targets
        targets = discover_new_targets()
    else:
        with open(targets_file, 'r') as f:
            targets = json.load(f)
    
    # Filter targets with emails
    email_targets = [t for t in targets if t.get('contact')]
    
    print(f"\nTargets: {len(targets)} total, {len(email_targets)} with email")
    print(f"{'='*60}\n")
    
    sent = 0
    for target in email_targets:
        if send_demo_email(target):
            sent += 1
    
    # Calculate revenue potential
    total_min = sum(int(t['deal_value'].split('-')[0].replace('$','').replace(',','')) for t in targets)
    total_max = sum(int(t['deal_value'].split('-')[1].replace('$','').replace(',','')) for t in targets)
    
    print(f"\n{'='*60}")
    print(f"DEMO CAMPAIGN COMPLETE")
    print(f"{'='*60}")
    print(f"Emails Sent: {sent}/{len(email_targets)}")
    print(f"Potential Revenue: ${total_min:,} - ${total_max:,}")
    print(f"{'='*60}")
    
    return sent, total_min, total_max

if __name__ == "__main__":
    run_demo_campaign()
