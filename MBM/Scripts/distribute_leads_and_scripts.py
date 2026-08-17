import json
import csv
import os
import sys
from datetime import datetime
from pathlib import Path

DATABASE_PATH = "mbm-dialer/app/public/leads_database.json"
NPI_CSV = "MBM/Artifacts/npi_verified_callsheet.csv"
RE_CSV = "us_real_estate_top_200_prospects.csv"

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from MBM.GLM.single_writer_lock import DialerSingleWriter
    _SINGLE_WRITER = DialerSingleWriter()
except Exception:
    _SINGLE_WRITER = None

# Pre-defined scripts per vertical
SCRIPTS = {
    "Real Estate Sellers": "Hi {contact}, this is Alex. I was calling about the property at {address}. I know this is out of the blue, but I was wondering if you've ever considered selling it?",
    "Real Estate Buyers": "Hey {contact}, it's Alex. I see you're buying properties in {city}. I have an off-market deal that might fit your criteria. Do you have a minute?",
    "Clinics": "Hi {contact}, I'm calling from MBM. We specialize in helping healthcare clinics like {company} scale their patient acquisition. Are you the right person to speak with about marketing?",
    "HVAC": "Hey {contact}, I noticed {company} has been doing a lot of work around {city}. We help HVAC businesses double their booked jobs. Do you have capacity for more jobs right now?",
    "B2B": "Hi {contact}, this is Alex. I'm reaching out because we help businesses like {company} automate their outreach. Is this something you're currently exploring?",
    "Default": "Hi {contact}, this is Alex. I'm reaching out regarding {company}. Do you have a brief moment?"
}

def load_json(path):
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return []

def load_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return list(csv.DictReader(f))

def get_script(vertical, contact, company, address, city):
    template = SCRIPTS.get(vertical, SCRIPTS["Default"])
    return template.format(
        contact=contact or "there",
        company=company or "your business",
        address=address or "your property",
        city=city or "your area"
    )

def run():
    print("Consolidating and distributing leads into sections...")
    
    # Load existing JSON database
    existing_leads = load_json(DATABASE_PATH)
    
    # Load CSV sources
    npi_leads = load_csv(NPI_CSV)
    re_leads = load_csv(RE_CSV)
    
    # Map existing by ID to avoid duplicates
    db_map = {lead['id']: lead for lead in existing_leads if 'id' in lead}
    
    # 1. Process NPI Clinics (100% verified real numbers)
    print(f"Processing {len(npi_leads)} NPI Clinic leads...")
    for i, row in enumerate(npi_leads):
        if not row.get('verified_phone') and not row.get('phone'): continue
        
        lead_id = f"Clinics-NPI-{i}"
        contact = row.get('authorized_official_name', '').title()
        if not contact: contact = "Owner/Manager"
        
        company = row.get('company_name', '').title()
        address = row.get('address', '')
        city = row.get('city', '').title()
        phone = row.get('verified_phone') or row.get('phone', '')
        
        if lead_id not in db_map:
            db_map[lead_id] = {
                "id": lead_id,
                "vertical": "Clinics",
                "company": company,
                "contact": contact,
                "phone": phone,
                "details": {
                    "City": city,
                    "State": row.get('state', ''),
                    "Address": address,
                    "Lead_Source": "CMS NPI Registry (Verified)",
                    "Taxonomy": row.get('taxonomy', '')
                }
            }
            
    # 2. Process RE CSV (assuming it's a mix of Buyers/Sellers)
    print(f"Processing {len(re_leads)} Real Estate leads...")
    for i, row in enumerate(re_leads):
        vertical = "Real Estate Sellers" if row.get('Prospect_Type', '').lower() == 'seller' else "Real Estate Buyers"
        lead_id = f"{vertical}-CSV-{i}"
        contact = row.get('Contact_Name', '').title()
        company = contact # for residential
        address = row.get('Property_or_Facility_Address', '')
        city = row.get('City', '').title()
        phone = row.get('Phone', '')
        
        if lead_id not in db_map:
            db_map[lead_id] = {
                "id": lead_id,
                "vertical": vertical,
                "company": company,
                "contact": contact,
                "phone": phone,
                "details": {
                    "City": city,
                    "State": row.get('State', ''),
                    "Address": address,
                    "Lead_Source": "Top 200 Prospects CSV",
                    "Score": row.get('Antigravity_Priority_Score', '')
                }
            }
            
    # 3. Apply Scripts to ALL leads
    print("Applying customized scripts to all leads...")
    for lead_id, lead in db_map.items():
        v = lead.get("vertical", "Default")
        c = lead.get("contact", "")
        comp = lead.get("company", "")
        addr = lead.get("details", {}).get("Address", "") or lead.get("details", {}).get("Property_Address", "")
        city = lead.get("details", {}).get("City", "")
        
        # Inject script into details
        lead["details"]["Call_Script"] = get_script(v, c, comp, addr, city)
        
    # Filter out empty phones or placeholders just to be clean
    final_list = [lead for lead in db_map.values() if lead.get("phone") and "ACTION_REQUIRED" not in lead.get("phone")]
    
    # Save back to database
    if _SINGLE_WRITER is not None:
        _SINGLE_WRITER.full_replace(final_list, author="DISTRIBUTE_LEADS_AND_SCRIPTS")
    else:
        with open(DATABASE_PATH, 'w', encoding='utf-8') as f:
            json.dump(final_list, f, indent=2)
        
    print(f"Success! {len(final_list)} total leads distributed into sections with verified scripts.")
    
    # Print summary
    summary = {}
    for l in final_list:
        v = l.get("vertical", "Unknown")
        summary[v] = summary.get(v, 0) + 1
    
    print("\nLead Distribution Summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")

if __name__ == "__main__":
    run()
