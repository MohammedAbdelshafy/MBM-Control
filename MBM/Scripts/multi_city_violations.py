"""
Multi-City Code Violation Scraper
=================================
Pulls code violations from DFW metro cities using free public APIs.
No API keys required - all from open data portals.
"""

import os
import csv
import json
import urllib.request
import urllib.parse
import ssl
from datetime import datetime, timedelta
from pathlib import Path

ssl._create_default_https_context = ssl._create_unverified_context

MBM_ROOT = r"C:\Users\omare\OneDrive\Desktop\AI\MBM"
ARTIFACTS = os.path.join(MBM_ROOT, "Artifacts")

# City Open Data API endpoints (Socrata)
CITY_APIS = {
    "Dallas": {
        "endpoint": "https://www.dallasopendata.com/resource/gc4d-8a49.json",
        "date_field": "created_date",
        "address_field": "address",
        "type_field": "service_request_type"
    },
    "Fort Worth": {
        "endpoint": "https://data.fortworth.gov/resource/7ygg-csw5.json",
        "date_field": "created_date",
        "address_field": "address",
        "type_field": "service_request_type"
    },
    "Arlington": {
        "endpoint": "https://data.arlingtontx.gov/resource/w8jn-tdh4.json",
        "date_field": "created_date",
        "address_field": "address",
        "type_field": "service_request_type"
    },
    "Plano": {
        "endpoint": "https://data.plano.gov/resource/yp9m-gxh2.json",
        "date_field": "created_date",
        "address_field": "address",
        "type_field": "service_request_type"
    },
    "Irving": {
        "endpoint": "https://data.irvingtx.gov/resource/ebnx-8j2y.json",
        "date_field": "created_date",
        "address_field": "address",
        "type_field": "service_request_type"
    },
    "Garland": {
        "endpoint": "https://data.garlandtx.gov/resource/u6j5-g7nb.json",
        "date_field": "created_date",
        "address_field": "address",
        "type_field": "service_request_type"
    },
    "Mesquite": {
        "endpoint": "https://data.mesquitetx.gov/resource/8d2j-p2y5.json",
        "date_field": "created_date",
        "address_field": "address",
        "type_field": "service_request_type"
    },
}

def pull_city_violations(city_name, config, days_back=30):
    """Pull violations from a single city's open data API."""
    leads = []
    
    date_threshold = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%dT00:00:00')
    
    # URL encode the $ character for Socrata
    url = f"{config['endpoint']}?%24where={config['date_field']}>=%27{date_threshold}%27&%24limit=500&%24order={config['date_field']}%20DESC"
    
    try:
        req = urllib.request.Request(url)
        req.add_header('User-Agent', 'Mozilla/5.0 (MBM-LeadEngine)')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            data = json.loads(response.read().decode())
        
        for record in data:
            address = record.get(config['address_field'], '')
            if not address:
                continue
            
            lead = {
                'Lead_Type': 'Distressed Seller',
                'Company': '',
                'Contact_Name': '',
                'Email': '',
                'Phone': '',
                'Website': '',
                'City': city_name,
                'State': 'TX',
                'Property_Address': f"{address}, {city_name}, TX",
                'Distress_Signal': record.get(config['type_field'], 'Code Violation'),
                'Signal_Date': record.get(config['date_field'], ''),
                'Owner_Name': '',
                'Lead_Source': f'{city_name} Open Data API',
                'Source_File': f'{city_name.lower().replace(" ", "_")}_311',
                'Status': 'New',
                'Confidence': '65',
                'QA_Status': 'Pending',
                'Verification_Status': 'Pending',
                'Notes': f"SR#: {record.get('service_request_number', record.get('sr_number', ''))} | Status: {record.get('status', '')}"
            }
            leads.append(lead)
        
        return leads
        
    except Exception as e:
        print(f"  [-] {city_name}: {e}")
        return []

def main():
    print("="*60)
    print("MULTI-CITY CODE VIOLATION LEAD COLLECTOR")
    print("="*60)
    
    all_leads = []
    
    for city_name, config in CITY_APIS.items():
        print(f"\n[*] Pulling {city_name}...")
        leads = pull_city_violations(city_name, config, days_back=60)
        all_leads.extend(leads)
        print(f"  [+] {city_name}: {len(leads)} violations found")
    
    # Load existing leads
    existing_file = None
    for f in sorted(Path(ARTIFACTS).glob("ALL_LEADS_FREE_*.csv"), reverse=True):
        existing_file = f
        break
    
    existing_leads = []
    if existing_file:
        with open(existing_file, 'r', encoding='utf-8') as fh:
            reader = csv.DictReader(fh)
            existing_leads = list(reader)
        print(f"\n[+] Existing leads loaded: {len(existing_leads)}")
    
    # Merge and deduplicate
    seen = set()
    merged = []
    
    for lead in existing_leads + all_leads:
        addr = lead.get('Property_Address', '').lower().strip()
        key = f"{lead.get('Lead_Type', '')}|{addr}"
        if key not in seen and addr:
            seen.add(key)
            merged.append(lead)
    
    # Write output
    output_file = os.path.join(ARTIFACTS, f"ALL_LEADS_MULTI_CITY_{datetime.now().strftime('%Y%m%d_%H%M')}.csv")
    fieldnames = ['Lead_Type', 'Company', 'Contact_Name', 'Email', 'Phone', 'Website', 'City', 'State', 'Property_Address', 'Distress_Signal', 'Signal_Date', 'Owner_Name', 'Lead_Source', 'Source_File', 'Status', 'Confidence', 'QA_Status', 'Verification_Status', 'Notes']
    
    with open(output_file, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(merged)
    
    wholesaler_count = sum(1 for l in merged if l['Lead_Type'] == 'Wholesaler/Buyer')
    distress_count = sum(1 for l in merged if l['Lead_Type'] == 'Distressed Seller')
    
    print(f"\n{'='*60}")
    print(f"MULTI-CITY LEAD REPORT")
    print(f"{'='*60}")
    print(f"Total Leads: {len(merged)}")
    print(f"  - Wholesalers/Buyers: {wholesaler_count}")
    print(f"  - Distressed Sellers: {distress_count}")
    print(f"\nNew violations added: {len(all_leads)}")
    print(f"Cities covered: {', '.join(CITY_APIS.keys())}")
    print(f"\nOutput: {output_file}")

import os
if __name__ == "__main__":
    main()
