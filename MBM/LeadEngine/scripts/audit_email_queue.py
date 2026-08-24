import os
import sys
import json
from pathlib import Path
from datetime import datetime

# Bootstrap path so we can load .env
BASE_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BASE_DIR.parent.parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

import requests
from dotenv import load_dotenv

load_dotenv(ROOT_DIR / ".env.local")

SUPABASE_URL = os.getenv("VITE_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Missing Supabase credentials.")
    sys.exit(1)

def run_audit():
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }
    
    print("Fetching email_queue from Supabase...")
    # Fetch all records without mutating
    response = requests.get(f"{SUPABASE_URL}/rest/v1/email_queue?status=eq.qued", headers=headers)
    
    if response.status_code != 200:
        print(f"Error fetching: {response.text}")
        return
        
    records = response.json()
    print(f"\n--- AUDIT OF email_queue ---")
    print(f"Total rows fetched: {len(records)}")
    
    statuses = {}
    for r in records:
        s = r.get("status", "unknown")
        statuses[s] = statuses.get(s, 0) + 1
        
    print("\nSTATUS COUNTS:")
    for k, v in statuses.items():
        print(f" - {k}: {v}")
        
    qued = [r for r in records if r.get("status") == "qued"]
    
    if not qued:
        print("No 'qued' rows found.")
        return
        
    unique_recipients = {}
    invalid = 0
    test_count = 0
    campaigns = {}
    dates = []
    
    for r in qued:
        raw_email = r.get("recipient_email") or ""
        email = raw_email.lower().strip()
        
        # Check invalid
        if "@" not in email or "." not in email:
            invalid += 1
            
        # Check test/internal
        if "test" in email or "example.com" in email or "abdelshafy" in email:
            test_count += 1
            
        if email not in unique_recipients:
            unique_recipients[email] = []
        unique_recipients[email].append(r)
        
        camp = r.get("campaign_id") or r.get("subject") or "UNKNOWN_CAMPAIGN"
        campaigns[camp] = campaigns.get(camp, 0) + 1
        
        if r.get("created_at"):
            dates.append(r.get("created_at"))
            
    dates.sort()
    
    duplicate_groups = {email: rows for email, rows in unique_recipients.items() if len(rows) > 1}
    normalized_duplicates = sum(len(rows) - 1 for rows in duplicate_groups.values())
    
    print("\nQUEUE CONTENT STATS (status='qued'):")
    print(f"Normalized Unique Recipients: {len(unique_recipients)}")
    print(f"Duplicate Recipient Rows: {normalized_duplicates}")
    print(f"Invalid Emails: {invalid}")
    print(f"Test/Internal Emails: {test_count}")
    print(f"Oldest timestamp: {dates[0] if dates else 'N/A'}")
    print(f"Newest timestamp: {dates[-1] if dates else 'N/A'}")
    
    print("\nCAMPAIGNS DETECTED:")
    for c, count in campaigns.items():
        print(f" - {c}: {count} leads")
        
    print(f"\nDUPLICATE GROUPS SUMMARY: {len(duplicate_groups)} unique emails have duplicates.")
    
    # Show exactly what would be retained without doing it
    retained_count = 0
    marked_dup_count = 0
    
    for email, rows in duplicate_groups.items():
        # Priority sort:
        # We prefer valid > provenance > oldest created_at > stable id
        def sort_key(row):
            is_test = 1 if "test" in (row.get("recipient_email") or "").lower() else 0
            created = row.get("created_at") or "9999"
            row_id = row.get("id") or 0
            return (is_test, created, row_id)
            
        sorted_rows = sorted(rows, key=sort_key)
        retained = sorted_rows[0]
        duplicates = sorted_rows[1:]
        
        retained_count += 1
        marked_dup_count += len(duplicates)
        
    print(f"\nIf deduplicated using deterministic priority:")
    print(f" - Retained queue rows: {retained_count} (1 per duplicate group)")
    print(f" - Marked as 'duplicate': {marked_dup_count}")

if __name__ == "__main__":
    run_audit()
