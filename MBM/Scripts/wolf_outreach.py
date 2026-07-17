"""
MBM AI Automation Agency - Wolf of Wall Street Sales System
===========================================================
AGGRESSIVE OUTREACH - HIGH ENERGY - CLOSE THE DEAL
"""

import os
import json
import csv
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

MBM_ROOT = r"C:\Users\omare\OneDrive\Desktop\AI\MBM"
SCRIPTS_DIR = os.path.join(MBM_ROOT, "Scripts")
CONTACTS_DIR = os.path.join(MBM_ROOT, "Contacts")

TODAY = datetime.now().strftime('%Y-%m-%d')

# Email config
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "abdelshafyclapps@gmail.com"
EMAIL_PASSWORD = "ffcd pjvx cmdf zbxg"

# WOLF OF WALL STREET ENERGY - OUTREACH TEMPLATES
TEMPLATES = {
    "cold_opener": {
        "subject": "I can save you 20 hours/week - seriously",
        "body": """Hey [NAME],

I'll cut straight to the chase. You're leaving money on the table.

I looked at [COMPANY] and found 3 things you're doing manually that AI can automate RIGHT NOW:

1. [PAIN_1] - This costs you [TIME_1] every week
2. [PAIN_2] - You're losing [MONEY_1] in missed opportunities  
3. [PAIN_3] - Your team wastes [TIME_2] on tasks a bot does in seconds

I built an AI system that does all of this. Costs less than a part-time employee, works 24/7, and never calls in sick.

Here's what I'm proposing:
- AI Lead Generation: Finds and qualifies prospects while you sleep
- Automated Follow-up: Never miss a lead again
- Smart CRM: Zero data entry, full pipeline visibility

Total investment: $2,500 setup + $500/month
ROI: 10x within 90 days or I work for free.

You in for a 15-minute call this week? I'll show you exactly how this works.

No fluff. No BS. Just results.

Mohammed Abdelshafy
AI Automation Specialist
+201040404118
abdelshafyclapps@gmail.com

P.S. I'm only taking on 3 more clients this month. First come, first served."""
    },
    
    "pain_point_email": {
        "subject": "[COMPANY] - I found $[MONEY] in lost revenue",
        "body": """[NAME],

I did some digging on [COMPANY]. Found something interesting.

You're losing approximately $[MONEY]/month from:
- Missed leads (no after-hours response)
- Manual data entry (errors + time waste)
- Slow follow-up (leads go cold in 5 minutes)

I built an AI system that fixes ALL of this. Here's the proof:

CLIENT RESULTS:
- 347% increase in lead response rate
- 89% reduction in manual data entry
- 2.5x more deals closed per month

The system costs $[PRICE]. The problem is costing you $[MONEY_LOST].

Let me show you how in 15 minutes. Calendar link: [CALENDAR]

Talk soon,
Mohammed Abdelshafy

P.S. I'm offering a free audit to the first 5 businesses that reply. No strings attached."""
    },
    
    "follow_up_1": {
        "subject": "Re: I can save you 20 hours/week - seriously",
        "body": """[NAME],

Following up. I know you're busy - that's exactly why you need this.

Quick question: What's your team's biggest time waster right now?

I can probably automate it. Let's talk.

Mohammed Abdelshafy
+201040404118"""
    },
    
    "follow_up_2": {
        "subject": "Last chance - AI automation pilot program",
        "body": """[NAME],

Final email. I'm closing the pilot program tomorrow.

3 spots left. 100% satisfaction guarantee. If it doesn't save you 20+ hours/week, full refund.

You in or out?

Mohammed Abdelshafy"""
    },
    
    "close_script": {
        "name": "WOLF CLOSE",
        "script": """
THE WOLF CLOSE - HIGH ENERGY, HIGH VALUE

1. OPEN WITH AUTHORITY:
"Look, I'm going to save you [X] hours and make you [Y] more deals. Period."

2. PAIN AGITATION:
"Right now, you're losing $[X]/month because [PAIN POINT]. Every day you wait, that's $[DAILY] walking out the door."

3. SOLUTION STACKING:
"I'm not selling you one thing. I'm giving you:
- AI Lead Gen (finds deals while you sleep)
- Auto Follow-up (never lose a lead)
- Smart CRM (zero data entry)
- 24/7 Chatbot (never miss an after-hours call)"

4. PRICE JUSTIFICATION:
"$2,500 + $500/month. Sounds like a lot? Let me ask you this:
- How many deals did you lose last month from slow follow-up?
- How many hours does your team waste on data entry?
- What's your average deal profit?

If you close ONE more deal per month, this pays for itself 10x over."

5. URGENCY CREATION:
"I'm taking 3 clients this month. After that, prices go up 40%. My calendar is open until [DATE]. That's it."

6. ASSUMED CLOSE:
"So we're looking at a start date of [DATE]. I'll send over the agreement now. You can pay via Venmo, Zelle, or wire. Which works best?"

7. HANDLING OBJECTIONS:
- "Too expensive" → "What's costing you MORE right now? The AI or the lost deals?"
- "Need to think about it" → "What specifically? I'll answer right now."
- "Not ready" → "When will you be ready? Let's schedule a follow-up. I'll hold your spot."
- "We have someone" → "Are they delivering 10x ROI? If not, let me show you the difference."

8. CLOSE WITH CONFIDENCE:
"We're doing this. I'll have the AI system live in [X] days. You're going to see results in the first week. Let's go."
"""
    }
}

def send_outreach(pain_point):
    """Send Wolf of Wall Street outreach to a pain point."""
    
    company = pain_point['business']
    email = pain_point.get('contact', '')
    solution = pain_point['solution']
    deal_value = pain_point['potential_deal']
    
    if not email:
        print(f"  [SKIP] No email for {company}")
        return False
    
    # Select template based on deal value
    template = TEMPLATES['cold_opener']
    
    # Personalize
    body = template['body']
    body = body.replace('[NAME]', company.split()[0])
    body = body.replace('[COMPANY]', company)
    body = body.replace('[PAIN_1]', pain_point['pain'][:50])
    body = body.replace('[PAIN_2]', 'manual lead management')
    body = body.replace('[PAIN_3]', 'slow response times')
    body = body.replace('[TIME_1]', '10+ hours')
    body = body.replace('[TIME_2]', '15+ hours')
    body = body.replace('[MONEY_1]', '$2,000+')
    body = body.replace('[PRICE]', deal_value.split('-')[0])
    
    subject = template['subject'].replace('[COMPANY]', company)
    
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
        
        print(f"  [OK] Sent to {company} ({email})")
        return True
    except Exception as e:
        print(f"  [FAIL] {company}: {e}")
        return False

def run_outreach_campaign():
    """Run aggressive outreach campaign."""
    print(f"{'='*60}")
    print(f"WOLF OF WALL STREET - OUTREACH CAMPAIGN")
    print(f"Date: {TODAY}")
    print(f"{'='*60}")
    
    # Load pain points
    pain_file = os.path.join(MBM_ROOT, "PainPoints", f"PAINPOINTS_{TODAY}.json")
    if not os.path.exists(pain_file):
        print("Running pain point discovery first...")
        from pain_point_discovery import discover_pain_points
        pain_points, pain_file = discover_pain_points()
    else:
        with open(pain_file, 'r') as f:
            pain_points = json.load(f)
    
    print(f"\nTargets: {len(pain_points)} businesses")
    print(f"{'='*60}\n")
    
    sent = 0
    for pp in pain_points:
        if send_outreach(pp):
            sent += 1
    
    # Save campaign log
    log_file = os.path.join(MBM_ROOT, "Logs", f"outreach_{TODAY}.json")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    log = {
        'date': TODAY,
        'targets': len(pain_points),
        'sent': sent,
        'companies': [pp['business'] for pp in pain_points],
        'potential_revenue': {
            'min': sum(int(pp['potential_deal'].split('-')[0].replace('$','').replace(',','')) for pp in pain_points),
            'max': sum(int(pp['potential_deal'].split('-')[1].replace('$','').replace(',','')) for pp in pain_points)
        }
    }
    with open(log_file, 'w') as f:
        json.dump(log, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"CAMPAIGN COMPLETE")
    print(f"{'='*60}")
    print(f"Emails Sent: {sent}/{len(pain_points)}")
    print(f"Potential Revenue: ${log['potential_revenue']['min']:,} - ${log['potential_revenue']['max']:,}")
    print(f"{'='*60}")
    
    return log

def print_close_script():
    """Print the Wolf of Wall Street close script."""
    print(TEMPLATES['close_script']['script'].encode('ascii', 'ignore').decode('ascii'))

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "close":
        print_close_script()
    else:
        run_outreach_campaign()
