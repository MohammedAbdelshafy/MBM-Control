"""
MBM AI Automation - Multi-Market Outreach Deploy
=================================================
Sends aggressive outreach to all 41 targets across 10 markets.
"""

import os
import json
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

MBM_ROOT = r"C:\Users\omare\OneDrive\Desktop\AI\MBM"
MULTI_MARKET_DIR = os.path.join(MBM_ROOT, "MultiMarket")

TODAY = datetime.now().strftime('%Y-%m-%d')

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "abdelshafyclapps@gmail.com"
EMAIL_PASSWORD = "ffcd pjvx cmdf zbxg"

# WOLF ENERGY TEMPLATES
TEMPLATES = {
    "blitz": {
        "subject": "AI will save you $50K/year - FREE demo inside",
        "body": """Hey,

I'll cut straight to the chase. Your competitors are automating. You're not.

I built an AI system that:
- Finds 50+ qualified leads/week (vs 10 manually)
- Follows up 24/7 (you sleep, it works)
- Never misses an after-hours lead
- Does data entry FOR YOU

RESULTS:
- 347% more lead responses
- 89% less manual work
- 3x more deals per month

Cost: $2,500 + $500/month
ROI: 13,000%+ in year one

I'm offering FREE demos to 5 businesses this week. After that, $500 consultation fee.

Reply "DEMO" for instant access.

Mohammed Abdelshafy
AI Automation Specialist
+201040404118
abdelshafyclapps@gmail.com

P.S. Every day you wait costs you $500 in lost deals."""
    },
    "pain_first": {
        "subject": "You're losing $10K/month - I can fix it",
        "body": """Hey,

Quick math:
- You spend 20+ hours/week on manual tasks
- You lose 15+ leads/week from slow response
- Your competitors automate while you sleep

This costs you: $10,000+/month in lost deals

My AI system fixes ALL of this.

Cost: $2,500 + $500/month
ROI: Pays for itself in 1 week

Free demo this week. Reply "DEMO".

Mohammed Abdelshafy
+201040404118"""
    },
    "social_proof": {
        "subject": "How I helped a wholesaler close 2 extra deals ($30K)",
        "body": """Hey,

Last week I showed my AI system to a DFW wholesaler.

Result: He closed 2 more deals that month. That's $30K extra revenue.

The system:
- AI finds qualified leads automatically
- Follow-up happens 24/7
- Zero data entry
- Never misses a lead

He invested $2,500. Made $30,000. That's 1,100% ROI in 30 days.

I'm offering FREE demos to 5 businesses this week.

Reply "DEMO" to see how this works.

Mohammed Abdelshafy
+201040404118"""
    }
}

def send_to_target(target, template_name="blitz"):
    """Send outreach to a target."""
    email = target.get('email', '')
    company = target.get('company', 'there')
    
    if not email:
        return False
    
    template = TEMPLATES[template_name]
    
    body = template['body']
    body = body.replace('[COMPANY]', company)
    body = body.replace('[MARKET]', target.get('market', 'your market'))
    
    subject = template['subject']
    subject = subject.replace('[COMPANY]', company)
    
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
        
        return True
    except Exception as e:
        return False

def deploy_outreach():
    """Deploy outreach to all markets."""
    print(f"{'='*70}")
    print(f"MBM AI AUTOMATION - MULTI-MARKET OUTREACH DEPLOY")
    print(f"Date: {TODAY}")
    print(f"{'='*70}")
    
    # Load all targets
    all_file = os.path.join(MULTI_MARKET_DIR, f"ALL_TARGETS_{TODAY}.json")
    if not os.path.exists(all_file):
        print("Running target discovery first...")
        from multi_market_targets import discover_all_markets
        targets = discover_all_markets()
    else:
        with open(all_file, 'r') as f:
            targets = json.load(f)
    
    print(f"\nDeploying to {len(targets)} targets across {len(set(t['market'] for t in targets))} markets")
    print(f"{'='*70}\n")
    
    results = {}
    sent = 0
    
    for target in targets:
        market = target['market']
        if market not in results:
            results[market] = {'sent': 0, 'failed': 0, 'total_deal': 0}
        
        if send_to_target(target):
            print(f"  [OK] {target['company']} ({market})")
            results[market]['sent'] += 1
            results[market]['total_deal'] += int(target['deal'])
            sent += 1
        else:
            print(f"  [FAIL] {target['company']} ({market})")
            results[market]['failed'] += 1
    
    # Summary
    total_deal = sum(r['total_deal'] for r in results.values())
    
    print(f"\n{'='*70}")
    print(f"DEPLOY COMPLETE")
    print(f"{'='*70}")
    print(f"\nBy Market:")
    for market, stats in results.items():
        print(f"  {market}: {stats['sent']} sent, ${stats['total_deal']:,} pipeline")
    
    print(f"\nTOTAL:")
    print(f"  Emails Sent: {sent}/{len(targets)}")
    print(f"  Total Pipeline: ${total_deal:,}")
    print(f"  Deals Needed for $10K/day: {total_deal // 10000}")
    print(f"{'='*70}")
    
    # Save log
    log_file = os.path.join(MBM_ROOT, "Logs", f"deploy_{TODAY}.json")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    log = {
        'date': TODAY,
        'total_targets': len(targets),
        'emails_sent': sent,
        'total_pipeline': total_deal,
        'markets': results
    }
    with open(log_file, 'w') as f:
        json.dump(log, f, indent=2)
    
    return log

if __name__ == "__main__":
    deploy_outreach()
