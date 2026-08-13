"""
MBM Agency Outreach - Seller Pack Sales
========================================
Sends tailored outreach to lead generation agencies offering our seller packs.

Usage:
  python agency_outreach.py [--dry-run] [--test-email YOUR_EMAIL]
"""

import os
import sys
import csv
import json
import smtplib
import time
import random
from datetime import datetime
from pathlib import Path
from email.message import EmailMessage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from dotenv import load_dotenv

from MBM.LeadEngine.contact_enrichment import ContactEnricher

load_dotenv()

BASE_DIR = Path(r'C:\Users\omare\OneDrive\Desktop\AI\MBM')
PACKS_DIR = BASE_DIR / 'SellerPacks'
LOGS_DIR = BASE_DIR / 'LeadEngine' / 'logs'
LOGS_DIR.mkdir(parents=True, exist_ok=True)

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
SENDER_EMAIL = os.getenv("MASTER_GMAIL", "abdelshafyclapps@gmail.com")
SENDER_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

DRY_RUN = "--dry-run" in sys.argv
TEST_EMAIL = None
for arg in sys.argv:
    if arg.startswith("--test-email"):
        idx = sys.argv.index(arg)
        if "=" in arg:
            TEST_EMAIL = arg.split("=")[1]
        elif idx + 1 < len(sys.argv):
            TEST_EMAIL = sys.argv[idx + 1]

def log(msg):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    line = f"[AGENCY OUTREACH] {timestamp} - {msg}"
    print(line)
    with open(LOGS_DIR / 'agency_outreach.log', 'a', encoding='utf-8') as f:
        f.write(line + '\n')


# ============================================================
# TARGET AGENCIES - Real lead gen companies that buy lead packs
# ============================================================

TARGET_AGENCIES = [
    # Tier 1: Large RE Lead Gen Agencies
    {
        "name": "Carrot",
        "contact": "Team",
        "email": "support@carrot.com",
        "type": "SaaS + Lead Gen",
        "notes": "10K+ investor clients, need lead data for their platform",
    },
    {
        "name": "Lead Generation RE",
        "contact": "Partnerships",
        "email": "info@leadgenerationre.com",
        "type": "Lead Gen Agency",
        "notes": "Specializes in motivated seller leads",
    },
    {
        "name": "REI Reply",
        "contact": "Team",
        "email": "hello@reiReply.com",
        "type": "Cold Calling + Lead Gen",
        "notes": "Cold calling service, needs leads to call",
    },
    {
        "name": "BiggerPockets Marketplace",
        "contact": "Deals Team",
        "email": "deals@biggerpockets.com",
        "type": "Marketplace",
        "notes": "Largest RE investor community, lead marketplace",
    },
    {
        "name": "Batch Leads",
        "contact": "Sales",
        "email": "sales@batchleads.io",
        "type": "Skip Tracing + Lead Gen",
        "notes": "Skip tracing platform, could resell enriched leads",
    },
    # Tier 2: Regional Wholesalers (DFW focused)
    {
        "name": "New Western",
        "contact": "Acquisitions",
        "email": "sales@newwestern.com",
        "type": "Wholesale Marketplace",
        "notes": "$91.9M volume, already in pipeline",
    },
    {
        "name": "Ellis Acquisitions",
        "contact": "Info",
        "email": "info@ellishomesource.com",
        "type": "Wholesaler",
        "notes": "$54.1M volume, already contacted",
    },
    {
        "name": "Ambition Group LLC",
        "contact": "Nathan",
        "email": "nathan@ambitionrealtygroup.com",
        "type": "Wholesaler",
        "notes": "$91.9M volume, high-end deals",
    },
    # Tier 3: Data Providers / Lead Gen SaaS
    {
        "name": "PropStream",
        "contact": "Partnerships",
        "email": "partners@propstream.com",
        "type": "Data Provider",
        "notes": "RE data platform, could resell our enriched data",
    },
    {
        "name": "REISkip",
        "contact": "Team",
        "email": "info@reiskip.com",
        "type": "Skip Tracing",
        "notes": "Skip tracing service, leads needed for verification",
    },
    {
        "name": "DealMachine",
        "contact": "Team",
        "email": "support@dealmachine.com",
        "type": "Lead Gen App",
        "notes": "Driving for dollars app, needs lead data",
    },
    {
        "name": "Privy",
        "contact": "Team",
        "email": "hello@privy.com",
        "type": "RE Data",
        "notes": "Real estate data analytics platform",
    },
    # Tier 4: Marketing Agencies (RE focused)
    {
        "name": "SEO for Real Estate",
        "contact": "Team",
        "email": "info@seoforrealestate.com",
        "type": "Marketing Agency",
        "notes": "RE marketing, could resell leads to their clients",
    },
    {
        "name": "Real Estate Marketing Pro",
        "contact": "Team",
        "email": "hello@realestatemarketingpro.com",
        "type": "Marketing Agency",
        "notes": "RE marketing services",
    },
]


# ============================================================
# EMAIL TEMPLATES
# ============================================================

def get_pack_email_template(agency, pack):
    """Generate personalized email for a specific agency and pack."""
    
    subject = f"DFW Seller Lead Pack - {pack['count']} Verified Leads (${pack['price']}/lead)"
    
    body = f"""Hi {agency['contact']},

I'm reaching out from MBM Lead Generation. We specialize in acquiring and verifying distressed real estate seller leads across the DFW metroplex.

We have an exclusive batch of {pack['count']} verified seller leads available right now:

PACK: {pack['name']}
- {pack['count']} verified contacts (email + phone)
- {pack['description']}
- Price: ${pack['price']}/lead
- Delivery: Same-day CSV via email

These are NOT recycled leads from a database. We pull directly from:
- Dallas County 311 code violations (public records)
- Pre-foreclosure filings (auction dates confirmed)
- Property tax delinquent records
- Cash buyer match data

Our verification process includes:
- Owner name matching to property records
- Phone number validation (carrier verified)
- Email deliverability check (MX record verified)
- Distress signal scoring (0-100)

We currently supply leads to {agency.get('type', 'real estate companies')} like {agency['name']}.

Would you be interested in a sample pack of 10 leads to test quality before committing?

Best regards,
MBM Lead Generation
{SENDER_EMAIL}

P.S. We can also do custom packs targeting specific zip codes, property types, or distress signals. Just let us know what your clients need."""
    
    return subject, body


def get_intro_email(agency):
    """Generate initial introduction email (not pack-specific)."""
    
    subject = f"Exclusive DFW Seller Leads - Partnership Opportunity"
    
    body = f"""Hi {agency['contact']},

I found {agency['name']} while researching top {agency.get('type', 'real estate')} companies and wanted to reach out.

We run an automated lead generation pipeline that pulls distressed seller data directly from public records in the DFW metroplex. Our system processes:

- 300-500 seller leads/day from Dallas County 311
- Pre-foreclosure filings with verified equity data
- Code violation properties (distressed sellers)
- Cash buyer matching data

We're looking for partners who can move this inventory. Here's what we offer:

TIER 1 - Premium Pack ($300/lead):
- Verified phone + email
- Property address + owner name
- Distress signal + equity estimate
- Min 20 leads per pack

TIER 2 - Standard Pack ($150/lead):
- Verified contact info
- Property address
- Basic distress signal
- Min 30 leads per pack

TIER 3 - Base Pack ($70/lead):
- Contact information
- Property address
- Lead source attribution
- Min 50 leads per pack

We can also do revenue share: 50/50 on any closed deals from our leads.

Are you open to a quick 10-minute call this week to discuss how we can feed leads into {agency['name']}'s pipeline?

Best regards,
MBM Lead Generation
{SENDER_EMAIL}"""
    
    return subject, body


# ============================================================
# SEND EMAIL
# ============================================================

def send_email(to_email, subject, body, attachments=None):
    """Send an email with optional attachments."""
    if DRY_RUN:
        log(f"DRY RUN: Would send to {to_email}: {subject}")
        return True
    
    if TEST_EMAIL:
        to_email = TEST_EMAIL
        log(f"TEST MODE: Redirecting to {to_email}")
    
    if not SENDER_PASSWORD or SENDER_PASSWORD == "your-app-password":
        log(f"Skipping email to {to_email}: Missing GMAIL_APP_PASSWORD")
        return False

    msg = MIMEMultipart()
    msg['Subject'] = str(subject).replace('\n', ' ').strip()
    msg['From'] = f"MBM Lead Generation <{SENDER_EMAIL}>"
    msg['To'] = str(to_email).replace('\n', '').strip()
    
    msg.attach(MIMEText(body, 'plain'))
    
    # Attach CSV files if provided
    if attachments:
        for filepath in attachments:
            if filepath.exists():
                with open(filepath, 'rb') as f:
                    part = MIMEBase('application', 'octet-stream')
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header('Content-Disposition', f'attachment; filename={filepath.name}')
                    msg.attach(part)

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
        log(f"Email sent to {to_email}")
        return True
    except Exception as e:
        log(f"Failed to send to {to_email}: {e}")
        return False


# ============================================================
# MAIN OUTREACH
# ============================================================

def run_outreach():
    """Execute the full agency outreach campaign."""
    log("=" * 60)
    log("STARTING AGENCY OUTREACH CAMPAIGN")
    log("=" * 60)
    
    # Load pack catalog
    catalog_file = PACKS_DIR / 'pack_catalog.json'
    if not catalog_file.exists():
        log("No pack catalog found. Run create_seller_packs.py first.")
        return
    
    with open(catalog_file, 'r', encoding='utf-8') as f:
        catalog = json.load(f)
    
    log(f"Loaded {len(catalog)} packs from catalog")
    
    sent = 0
    errors = 0
    
    enricher = ContactEnricher()
    
    # Send intro emails to all agencies
    for agency in TARGET_AGENCIES:
        log(f"Enriching {agency['name']} via LinkedIn Sales Navigator...")
        dm_results = enricher.search_linkedin_decision_maker(agency['name'])
        if dm_results:
            dm = dm_results[0]
            agency['contact'] = dm['name']
            agency['linkedin'] = dm['linkedin']
            agency['title'] = dm['title']
            log(f"Found Decision Maker: {dm['name']} - {dm['title']}")
        
        subject, body = get_intro_email(agency)
        success = send_email(agency['email'], subject, body)
        
        if success:
            sent += 1
            log(f"Intro sent to {agency['name']} ({agency['email']})")
        else:
            errors += 1
        
        time.sleep(random.uniform(3, 7))
    
    # Send pack-specific emails to top agencies with sample attachment
    sample_pack = None
    for pack in catalog:
        if pack['tier'] == 'Premium' and pack['count'] > 0:
            # Find the CSV file
            for csv_file in PACKS_DIR.glob('*.csv'):
                if 'wholesale' in csv_file.name.lower() or 'distressed' in csv_file.name.lower():
                    sample_pack = pack
                    sample_file = csv_file
                    break
            break
    
    if sample_pack:
        # Send to top 5 agencies with sample pack
        top_agencies = [a for a in TARGET_AGENCIES[:5]]
        for agency in top_agencies:
            subject, body = get_pack_email_template(agency, sample_pack)
            success = send_email(agency['email'], subject, body, attachments=[sample_file])
            
            if success:
                sent += 1
                log(f"Pack offer sent to {agency['name']} with sample")
            else:
                errors += 1
            
            time.sleep(random.uniform(5, 10))
    
    # Summary
    summary = f"""
{'='*60}
AGENCY OUTREACH COMPLETE
{'='*60}
Emails sent: {sent}
Errors: {errors}
Agencies contacted: {len(TARGET_AGENCIES)}
Packs available: {len(catalog)}

PACKS CREATED:
"""
    for pack in catalog:
        summary += f"  - {pack['name']}: {pack['count']} leads @ ${pack['price']}/lead = ${pack['total_value']:,}\n"
    
    summary += f"\nTotal inventory value: ${sum(p['total_value'] for p in catalog):,}"
    summary += f"\n{'='*60}"
    
    print(summary)
    
    # Save outreach log
    log_file = LOGS_DIR / f"agency_outreach_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(log_file, 'w', encoding='utf-8') as f:
        json.dump({
            'timestamp': datetime.now().isoformat(),
            'agencies_contacted': len(TARGET_AGENCIES),
            'emails_sent': sent,
            'errors': errors,
            'packs': catalog,
        }, f, indent=2)
    
    return sent, errors


if __name__ == '__main__':
    if TEST_EMAIL:
        log(f"TEST MODE: All emails will be sent to {TEST_EMAIL}")
    
    sent, errors = run_outreach()
    
    print(f"\nTo send to yourself instead, run:")
    print(f"  python agency_outreach.py --test-email your@email.com")
