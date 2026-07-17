"""
MBM Daily Lead Pack Generator
==============================
Runs daily to collect leads from all free sources.
Creates date-stamped lead packs for agency sales.
Automatically emails seller packs to wholesalers.

Usage: python daily_lead_pack.py
"""

import os
import csv
import json
import urllib.request
import urllib.parse
import ssl
import smtplib
import sys
from datetime import datetime, timedelta
from pathlib import Path
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

ssl._create_default_https_context = ssl._create_unverified_context

MBM_ROOT = r"C:\Users\omare\OneDrive\Desktop\AI\MBM"
ARTIFACTS = os.path.join(MBM_ROOT, "Artifacts")
PACKS_DIR = os.path.join(MBM_ROOT, "LeadPacks")
LOGS_DIR = os.path.join(MBM_ROOT, "Logs")
CONTACTS_DIR = os.path.join(MBM_ROOT, "Contacts")

os.makedirs(PACKS_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
os.makedirs(CONTACTS_DIR, exist_ok=True)

TODAY = datetime.now().strftime('%Y-%m-%d')

# Email config
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_ADDRESS = "abdelshafyclapps@gmail.com"
EMAIL_PASSWORD = "ffcd pjvx cmdf zbxg"

# Seller pack pricing
PRICING = {
    "daily": "$25/day",
    "full_pack": "$40/day",
    "monthly": "$500/month"
}

def load_contacts():
    """Load wholesaler contacts from CSV."""
    contacts_file = os.path.join(CONTACTS_DIR, "wholesaler_targets.csv")
    if not os.path.exists(contacts_file):
        # Create default contacts file
        defaults = [
            {"company": "PipHouse LLC", "email": "PipHousellc@gmail.com", "phone": "469-658-4582", "status": "active", "added": TODAY},
            {"company": "Swift Home Solutions", "email": "investments@swifthomesolutions.com", "phone": "469-273-1235", "status": "active", "added": TODAY},
            {"company": "Diamond Acquisitions", "email": "diamondacquisitions@outlook.com", "phone": "469-436-4884", "status": "active", "added": TODAY},
        ]
        with open(contacts_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=["company", "email", "phone", "status", "added", "last_sent", "responses"])
            writer.writeheader()
            writer.writerows(defaults)
        return defaults
    
    contacts = []
    with open(contacts_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('status', 'active') == 'active':
                contacts.append(row)
    return contacts

def save_contacts(contacts):
    """Save contacts back to CSV."""
    contacts_file = os.path.join(CONTACTS_DIR, "wholesaler_targets.csv")
    with open(contacts_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=["company", "email", "phone", "status", "added", "last_sent", "responses"])
        writer.writeheader()
        writer.writerows(contacts)

def add_contact(company, email, phone=""):
    """Add a new wholesaler contact."""
    contacts = load_contacts()
    
    # Check if already exists
    for c in contacts:
        if c['email'] == email:
            print(f"  Contact already exists: {company}")
            return False
    
    new_contact = {
        "company": company,
        "email": email,
        "phone": phone,
        "status": "active",
        "added": TODAY,
        "last_sent": "",
        "responses": "0"
    }
    contacts.append(new_contact)
    save_contacts(contacts)
    print(f"  Added: {company} ({email})")
    return True

def pull_dallas_311():
    """Pull Dallas 311 code violations from open API."""
    leads = []
    url = "https://www.dallasopendata.com/resource/gc4d-8a49.json?%24limit=500&%24order=created_date%20DESC"
    
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0')
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode())
        
        for r in data:
            addr = r.get('address', '')
            if not addr:
                continue
            leads.append({
                'Lead_Type': 'Distressed Seller',
                'Property_Address': f"{addr}, Dallas, TX",
                'City': 'Dallas',
                'Owner_Name': '',
                'Phone': '',
                'Email': '',
                'Distress_Signal': r.get('service_request_type', 'Code Violation'),
                'Signal_Date': r.get('created_date', ''),
                'Lead_Source': 'Dallas 311 API',
                'Confidence': '70',
                'Notes': f"SR#{r.get('service_request_number','')}"
            })
    except Exception as e:
        print(f"  [!] Dallas 311 error: {e}")
    
    return leads

def pull_osm_leads():
    """Pull real estate businesses from OpenStreetMap."""
    leads = []
    query = '[out:json][timeout:60];area["name"="Dallas"]["admin_level"="8"]->.a;(node["office"="estate_agent"](area.a);node["shop"="real_estate_agent"](area.a);node["office"="property_management"](area.a););out body;'
    
    try:
        data = urllib.parse.urlencode({'data': query}).encode()
        req = urllib.request.Request('https://overpass-api.de/api/interpreter', data=data)
        req.add_header('User-Agent', 'MBM-LeadEngine/1.0')
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode())
        
        for el in result.get('elements', []):
            tags = el.get('tags', {})
            name = tags.get('name', '')
            if not name:
                continue
            leads.append({
                'Lead_Type': 'Wholesaler/Buyer',
                'Company': name,
                'Contact_Name': tags.get('contact:name', ''),
                'Phone': tags.get('contact:phone', tags.get('phone', '')),
                'Email': tags.get('contact:email', tags.get('email', '')),
                'Website': tags.get('website', ''),
                'City': tags.get('addr:city', 'Dallas'),
                'Lead_Source': 'OpenStreetMap',
                'Confidence': '60',
                'Notes': f"OSM ID: {el.get('id')}"
            })
    except Exception as e:
        print(f"  [!] OSM error: {e}")
    
    return leads

def pull_web_directory_leads():
    """Pre-compiled verified wholesaler leads."""
    return [
        {'Lead_Type':'Wholesaler/Buyer','Company':'New Western','City':'Dallas, TX','Website':'https://newwestern.com','Lead_Source':'KeyCrew','Confidence':'80','Notes':'Largest wholesale marketplace'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'Swift Home Solutions','City':'Dallas, TX','Website':'https://swifthomesolutions.com','Lead_Source':'KeyCrew','Confidence':'75','Notes':'DFW + San Antonio'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'No Worries Home Sale','City':'Fort Worth, TX','Website':'https://noworrieshomesale.com','Lead_Source':'KeyCrew','Confidence':'75','Notes':'Foreclosure, divorce, inherited'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'We Buy Houses Fast Dallas','City':'Dallas, TX','Website':'https://webuyhousesfastdallas.com','Lead_Source':'KeyCrew','Confidence':'75','Notes':'Residential, multi-family, commercial'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'Fliplist.com','City':'Dallas, TX','Website':'https://fliplist.com','Lead_Source':'KeyCrew','Confidence':'70','Notes':'Off-market marketplace'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'Property Ezer','City':'Dallas, TX','Website':'https://propertyezer.com','Lead_Source':'KeyCrew','Confidence':'70','Notes':'61+ TX locations'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'Alpha Cash Buyers','City':'Fort Worth, TX','Website':'https://alphacashbuyers.com','Lead_Source':'KeyCrew','Confidence':'70','Notes':'Cash buyer Fort Worth'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'A-List Homes LLC','City':'Dallas, TX','Website':'https://alishomes.com','Lead_Source':'KeyCrew','Confidence':'70','Notes':'Senior transition specialist'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'LUSH Property Solutions','City':'Dallas, TX','Website':'https://lushpropertysolutions.com','Lead_Source':'KeyCrew','Confidence':'70','Notes':'DFW wholesale + flip'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'Easy Offer DFW','City':'Dallas, TX','Website':'https://easyofferdfw.com','Lead_Source':'KeyCrew','Confidence':'70','Notes':'Cash buyer DFW'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'NetWorth Realty','City':'Dallas, TX','Website':'https://networthrealty.com','Lead_Source':'KeyCrew','Confidence':'70','Notes':'Distressed properties nationwide'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'AO Investments Group','City':'Dallas, TX','Website':'https://aoinvestmentsgroup.com','Lead_Source':'KeyCrew','Confidence':'70','Notes':'FL/TX/GA since 2012'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'MyHouseDeals','City':'Dallas, TX','Website':'https://myhousedeals.com','Lead_Source':'KeyCrew','Confidence':'70','Notes':'National platform 30+ states'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'Dallas Cash Home Buyers','City':'Dallas, TX','Website':'https://dallascashhomebuyers.com','Lead_Source':'Web','Confidence':'70','Notes':'5751 Arlington Park Dr'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'NTX Property Group','City':'Dallas, TX','Website':'https://ntxpropertygroup.com','Lead_Source':'Web','Confidence':'65','Notes':'North Texas wholesaling'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'DFW Wholesale Properties','City':'Dallas, TX','Website':'https://dfwwholesaleproperties.com','Lead_Source':'Web','Confidence':'65','Notes':'DFW wholesale'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'DFW Deal Board','City':'Dallas, TX','Website':'https://dfwdealboard.com','Lead_Source':'Web','Confidence':'65','Notes':'DFW deal board'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'Ali Abtin','City':'Dallas, TX','Lead_Source':'HouseCashin','Confidence':'65','Notes':'Top wholesaler'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'Niko Martillo','City':'Dallas, TX','Lead_Source':'HouseCashin','Confidence':'65','Notes':'Top wholesaler'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'Shanesse Roye','City':'Dallas, TX','Lead_Source':'HouseCashin','Confidence':'65','Notes':'Top wholesaler'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'VeriServe Solutions','City':'Dallas, TX','Lead_Source':'HouseCashin','Confidence':'65','Notes':'Top wholesaler'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'Preferred Luxury Rentals & Equity','City':'Dallas, TX','Lead_Source':'RealEstateBees','Confidence':'60','Notes':'Multi-state wholesaler'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'Turner & Partners LLC','City':'Dallas, TX','Lead_Source':'RealEstateBees','Confidence':'65','Notes':'100+ assignments since 2020'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'AirBorn Estate LLC','City':'Dallas, TX','Lead_Source':'RealEstateBees','Confidence':'60','Notes':'Phone: 813-683-2574'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'Leal Enterprises LLC','City':'Dallas, TX','Lead_Source':'RealEstateBees','Confidence':'65','Notes':'Zarek Scott Leal, Managing Partner'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'PipHouse LLC','City':'Dallas, TX','Lead_Source':'BiggerPockets','Confidence':'65','Notes':'Active DFW wholesaler'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'DFW REI Club','City':'Fort Worth, TX','Lead_Source':'REI Club','Confidence':'60','Notes':'Robin Carriger, 817-300-1132'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'Wholesale Tank','City':'Dallas, TX','Lead_Source':'RealEstateBees','Confidence':'60','Notes':'Funds EMD for wholesalers'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'CDL Holdings','City':'Dallas, TX','Lead_Source':'RealEstateBees','Confidence':'60','Notes':'Wholesale + fix and flip'},
        {'Lead_Type':'Wholesaler/Buyer','Company':'Mindful Investors','City':'Dallas, TX','Lead_Source':'RealEstateBees','Confidence':'60','Notes':'Southern states focus'},
    ]

def send_seller_pack(distressed, contacts, pack_dir):
    """Send seller lead pack to wholesaler contacts."""
    print("\n[EMAIL] Sending seller packs to wholesalers...")
    
    if not distressed:
        print("  No seller leads to send")
        return 0
    
    if not contacts:
        print("  No contacts to send to")
        return 0
    
    # Create temp seller file
    temp_file = os.path.join(pack_dir, f"temp_sellers_{TODAY}.csv")
    fieldnames = ['Lead_Type', 'Company', 'Contact_Name', 'Phone', 'Email', 'Website', 'City', 'State', 'Property_Address', 'Distress_Signal', 'Signal_Date', 'Owner_Name', 'Lead_Source', 'Confidence', 'Notes']
    with open(temp_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(distressed)
    
    # Email body
    body = f"""Hi,

Here is today's DFW Distressed Seller Lead Pack ({TODAY}).

STATS:
- Total Leads: {len(distressed)}
- Source: Dallas 311 Code Violations
- Coverage: Dallas/Fort Worth Metro

The attached CSV contains:
- Property addresses
- Distress signals (code violations, substandard structures)
- Date reported
- Confidence scores

These are fresh, daily-updated leads from Dallas County public records.

PRICING:
- $25/day (seller pack only)
- $40/day (full pack with wholesalers)
- $500/month (unlimited)

Reply to this email to subscribe or ask questions.

Best,
Mohammed Abdelshafy
+201040404118
abdelshafyclapps@gmail.com
"""
    
    sent = 0
    for contact in contacts:
        try:
            msg = MIMEMultipart()
            msg['From'] = EMAIL_ADDRESS
            msg['To'] = contact['email']
            msg['Subject'] = f"DFW Seller Leads {TODAY} - {len(distressed)} Distressed Properties"
            msg.attach(MIMEText(body, 'plain'))
            
            with open(temp_file, 'rb') as f:
                part = MIMEBase('application', 'octet-stream')
                part.set_payload(f.read())
                encoders.encode_base64(part)
                part.add_header('Content-Disposition', f'attachment; filename=SELLERS_{TODAY}.csv')
                msg.attach(part)
            
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()
            
            print(f"  [OK] Sent to {contact['company']} ({contact['email']})")
            sent += 1
            
            # Update last_sent date
            contact['last_sent'] = TODAY
        except Exception as e:
            print(f"  [FAIL] {contact['company']}: {e}")
    
    # Save updated contacts
    save_contacts(contacts)
    
    # Cleanup temp file
    if os.path.exists(temp_file):
        os.remove(temp_file)
    
    print(f"  Sent {sent}/{len(contacts)} emails")
    return sent

def generate_lead_pack():
    """Generate today's lead pack."""
    print(f"{'='*60}")
    print(f"MBM DAILY LEAD PACK GENERATOR")
    print(f"Date: {TODAY}")
    print(f"{'='*60}")
    
    all_leads = []
    
    # 1. Dallas 311 Code Violations
    print("\n[1/3] Pulling Dallas 311 violations...")
    leads = pull_dallas_311()
    all_leads.extend(leads)
    print(f"  -> {len(leads)} violations")
    
    # 2. OpenStreetMap businesses
    print("[2/3] Pulling OpenStreetMap businesses...")
    leads = pull_osm_leads()
    all_leads.extend(leads)
    print(f"  -> {len(leads)} businesses")
    
    # 3. Web directory leads
    print("[3/3] Loading web directory leads...")
    leads = pull_web_directory_leads()
    all_leads.extend(leads)
    print(f"  -> {len(leads)} wholesalers")
    
    # Deduplicate
    seen = set()
    deduped = []
    for lead in all_leads:
        key = f"{lead.get('Company', '')}|{lead.get('Property_Address', '')}".lower()
        if key not in seen:
            seen.add(key)
            deduped.append(lead)
    
    # Split by type
    wholesalers = [l for l in deduped if l['Lead_Type'] == 'Wholesaler/Buyer']
    distressed = [l for l in deduped if l['Lead_Type'] == 'Distressed Seller']
    
    # Create pack directory
    pack_dir = os.path.join(PACKS_DIR, f"Pack_{TODAY}")
    os.makedirs(pack_dir, exist_ok=True)
    
    # Write full pack
    full_path = os.path.join(pack_dir, f"FULL_PACK_{TODAY}.csv")
    fieldnames = ['Lead_Type', 'Company', 'Contact_Name', 'Phone', 'Email', 'Website', 'City', 'State', 'Property_Address', 'Distress_Signal', 'Signal_Date', 'Owner_Name', 'Lead_Source', 'Confidence', 'Notes']
    
    with open(full_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(deduped)
    
    # Write wholesaler pack
    wholesale_path = os.path.join(pack_dir, f"WHOLESALERS_{TODAY}.csv")
    with open(wholesale_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(wholesalers)
    
    # Write distressed seller pack
    distressed_path = os.path.join(pack_dir, f"DISTRESSED_SELLERS_{TODAY}.csv")
    with open(distressed_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(distressed)
    
    # Write manifest
    manifest = {
        'date': TODAY,
        'generated_at': datetime.now().isoformat(),
        'total_leads': len(deduped),
        'wholesalers': len(wholesalers),
        'distressed_sellers': len(distressed),
        'sources': list(set(l.get('Lead_Source', '') for l in deduped)),
        'cities': list(set(l.get('City', '') for l in deduped)),
        'files': {
            'full_pack': full_path,
            'wholesalers': wholesale_path,
            'distressed_sellers': distressed_path
        }
    }
    
    manifest_path = os.path.join(pack_dir, f"MANIFEST_{TODAY}.json")
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)
    
    # Log
    log_path = os.path.join(LOGS_DIR, f"daily_pack_{TODAY}.log")
    with open(log_path, 'w') as f:
        f.write(f"Daily Lead Pack Generated: {TODAY}\n")
        f.write(f"Total: {len(deduped)} | Wholesalers: {len(wholesalers)} | Distressed: {len(distressed)}\n")
        f.write(f"Sources: {', '.join(manifest['sources'])}\n")
        f.write(f"Output: {pack_dir}\n")
    
    print(f"\n{'='*60}")
    print(f"LEAD PACK GENERATED SUCCESSFULLY")
    print(f"{'='*60}")
    print(f"Total Leads: {len(deduped)}")
    print(f"  Wholesalers/Buyers: {len(wholesalers)}")
    print(f"  Distressed Sellers: {len(distressed)}")
    print(f"\nPack Location: {pack_dir}")
    print(f"Files:")
    print(f"  - {os.path.basename(full_path)}")
    print(f"  - {os.path.basename(wholesale_path)}")
    print(f"  - {os.path.basename(distressed_path)}")
    print(f"  - {os.path.basename(manifest_path)}")
    
    # Send to wholesalers
    contacts = load_contacts()
    send_seller_pack(distressed, contacts, pack_dir)
    
    return pack_dir, manifest

if __name__ == "__main__":
    # Check for add contact command
    if len(sys.argv) > 1 and sys.argv[1] == "add":
        if len(sys.argv) >= 4:
            company = sys.argv[2]
            email = sys.argv[3]
            phone = sys.argv[4] if len(sys.argv) > 4 else ""
            add_contact(company, email, phone)
        else:
            print("Usage: python daily_lead_pack.py add <company> <email> [phone]")
    else:
        generate_lead_pack()
