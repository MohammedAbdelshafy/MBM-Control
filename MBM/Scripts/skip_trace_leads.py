import csv
import os
import random
import time
import urllib.parse
from datetime import datetime
import requests
from bs4 import BeautifulSoup

# Path Configuration
WORKSPACE_LEADS = r"C:\Users\omare\OneDrive\Desktop\AI\MBM\Clients\BAGA\Dallas_Distressed_Batch_01_2026-07-04.csv"
DESKTOP_LEADS = r"C:\Users\omare\OneDrive\Desktop\leads\Dallas_Distressed_Batch_01_2026-07-04.csv"

# Pre-researched high-priority property owners
RESEARCHED_OWNERS = {
    "9957 BURNHAM DR, DALLAS, TX, 75243": {
        "Owner_Name": "CODY ADAMS",
        "Phone": "214-528-7690"
    },
    "9916 ACKLIN DR, DALLAS, TX, 75243": {
        "Owner_Name": "CHRIS D KOEBERLE",
        "Phone": "214-349-4102"
    },
    "13102 HALWIN CIR, DALLAS, TX, 75243": {
        "Owner_Name": "ON Q PROPERTY MGMT (RENTAL)",
        "Phone": "480-696-6776"
    },
    "9939 BURNHAM DR, DALLAS, TX, 75243": {
        "Owner_Name": "DERRICK ADAMS",
        "Phone": "214-575-8933"
    },
    "10062 ROYAL LN, DALLAS, TX, 75238": {
        "Owner_Name": "COUNTRY SQUIRE VENTURE",
        "Phone": "972-241-1188"
    },
    "10255 BLACK HICKORY RD, DALLAS, TX, 75243": {
        "Owner_Name": "GARY BARKEY",
        "Phone": "972-437-9811"
    },
    "9218 LEASIDE DR, DALLAS, TX, 75238": {
        "Owner_Name": "JOHN PIROZZOLO",
        "Phone": "214-349-5818"
    }
}

# Lazy-load the free skip tracer
_free_tracer = None

def get_free_tracer():
    global _free_tracer
    if _free_tracer is None:
        try:
            import sys
            sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'LeadEngine'))
            from free_skip_tracer import FreeSkipTracer
            _free_tracer = FreeSkipTracer()
        except ImportError:
            pass
    return _free_tracer


def scrape_contact_info(address: str):
    """
    Attempts to scrape contact info for the given address using free public directories.
    NO fake data generation — returns (None, None) if nothing found.
    """
    tracer = get_free_tracer()
    if tracer:
        try:
            result = tracer.find_contact(address=address, city="Dallas")
            phone = result.get("phone")
            name = result.get("email")  # We'll use the name from CSV if available
            if phone:
                print(f"[+] Free Skip Tracer found phone for {address}: {phone} (source: {result.get('source')})")
                return None, phone
        except Exception as e:
            print(f"[-] Free Skip Tracer error: {e}")

    # Fallback: try fastpeoplesearch directly
    try:
        parts = address.split(",")
        if len(parts) >= 3:
            street = parts[0].strip()
            city_state_zip = ",".join(parts[1:]).strip()
        else:
            street = address
            city_state_zip = ""

        url = f"https://www.fastpeoplesearch.com/address/{urllib.parse.quote(street.replace(' ', '-'))}_{urllib.parse.quote(city_state_zip.replace(' ', '-'))}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        }
        resp = requests.get(url, headers=headers, timeout=5)

        if resp.status_code == 200 and "Cloudflare" not in resp.text:
            soup = BeautifulSoup(resp.text, 'html.parser')
            name_elem = soup.select_one("h2.fullname") or soup.select_one(".name-link")
            phone_elem = soup.select_one("a[href^='tel:']")

            name = name_elem.text.strip().upper() if name_elem else None
            phone = phone_elem.text.strip() if phone_elem else None

            if name and phone:
                print(f"[+] Scraped real data for {address}: {name} / {phone}")
                return name, phone

    except Exception as e:
        pass

    # NO fake data — return None so the caller knows we couldn't find it
    print(f"[-] No contact data found for {address}")
    return None, None

def skip_trace():
    print("[*] Starting Skip-Tracing Module (FREE sources only — NO fake data)...")
    
    if not os.path.exists(WORKSPACE_LEADS):
        print(f"[-] Error: Base file {WORKSPACE_LEADS} does not exist.")
        return
        
    leads = []
    enriched_count = 0
    failed_count = 0
    
    with open(WORKSPACE_LEADS, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        for row in reader:
            addr = row.get("Property_Address", "")
            
            # 1. Check if we have pre-researched owner details
            if addr in RESEARCHED_OWNERS:
                row["Owner_Name"] = RESEARCHED_OWNERS[addr]["Owner_Name"]
                row["Phone"] = RESEARCHED_OWNERS[addr]["Phone"]
                enriched_count += 1
            else:
                # 2. Use free skip tracing sources (NO fake data fallback)
                name, phone = scrape_contact_info(addr)
                if name:
                    row["Owner_Name"] = name
                if phone:
                    row["Phone"] = phone
                    enriched_count += 1
                else:
                    failed_count += 1
                    print(f"[!] No phone found for: {addr}")
                # sleep to avoid rate limits
                time.sleep(random.uniform(0.5, 1.5))
                
            leads.append(row)
            
    # Write back to Workspace Leads CSV
    with open(WORKSPACE_LEADS, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(leads)
    print(f"[+] Workspace file updated: {WORKSPACE_LEADS}")
    
    # Write back to Desktop Leads CSV
    os.makedirs(os.path.dirname(DESKTOP_LEADS), exist_ok=True)
    with open(DESKTOP_LEADS, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(leads)
    print(f"[+] Desktop file updated: {DESKTOP_LEADS}")
    print(f"[+] Skip-trace complete: {enriched_count} enriched, {failed_count} not found (NO fake data)")
    print(f"[+] Total leads processed: {len(leads)}")

if __name__ == "__main__":
    skip_trace()
