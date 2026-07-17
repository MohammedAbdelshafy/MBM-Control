import requests
import csv
import os
from datetime import datetime

# Configuration
# Endpoint for Dallas 311 Service Requests
API_URL = "https://www.dallasopendata.com/resource/gc4d-8a49.json"
LIMIT = 100

# Filters for distressed indicators
QUERY = {
    "$where": "service_request_type like '%Concern%' OR service_request_type like '%Rental%' OR service_request_type like '%Boarding%' OR service_request_type like '%Dumping%'",
    "$limit": LIMIT,
    "$order": "created_date DESC"
}

ARTIFACT_DIR = r"C:\Users\omare\OneDrive\Desktop\AI\MBM\Artifacts"
LOG_DIR = r"C:\Users\omare\OneDrive\Desktop\AI\MBM\Logs"

def collect_evidence():
    print(f"[*] Targeting Dallas Open Data: {API_URL}")
    print("[*] Fetching distressed property indicators...")
    
    try:
        response = requests.get(API_URL, params=QUERY, timeout=15)
        
        # Fallback to another Dallas 311 dataset ID if 404
        if response.status_code == 404:
            print("[!] Default 311 ID failed. Trying alternative dataset ID (se4q-erqg)...")
            alt_url = "https://www.dallasopendata.com/resource/se4q-erqg.json"
            response = requests.get(alt_url, params=QUERY, timeout=15)
            
        response.raise_for_status()
        data = response.json()
        
        if not data:
            print("[!] No records returned from the API.")
            return

        date_str = datetime.now().strftime("%Y-%m-%d")
        csv_path = os.path.join(ARTIFACT_DIR, f"raw_leads_Dallas_311_{date_str}.csv")
        
        # Ensure dir exists
        os.makedirs(ARTIFACT_DIR, exist_ok=True)
        os.makedirs(LOG_DIR, exist_ok=True)

        # Write Raw Data
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            if len(data) > 0:
                headers = set()
                for row in data:
                    headers.update(row.keys())
                writer = csv.DictWriter(f, fieldnames=sorted(list(headers)))
                writer.writeheader()
                for row in data:
                    writer.writerow(row)
                    
        print(f"[+] Successfully extracted {len(data)} raw records.")
        print(f"[+] Evidence saved to: {csv_path}")
        
        # Log the action
        with open(os.path.join(LOG_DIR, "Decision_Log.md"), 'a', encoding='utf-8') as log:
            log.write(f"\n- **{datetime.now().isoformat()}**: `evidence-collector` fetched {len(data)} records from Dallas Open Data API. Filters applied: High Weeds/Substandard/Vacant. Artifact: `{csv_path}`\n")
            
    except Exception as e:
        print(f"[-] Evidence collection failed: {e}")

if __name__ == "__main__":
    collect_evidence()
