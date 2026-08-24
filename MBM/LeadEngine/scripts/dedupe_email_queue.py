import os
import sys
import json
from pathlib import Path
from datetime import datetime
import requests
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BASE_DIR.parent.parent.parent.resolve()
sys.path.insert(0, str(ROOT_DIR))

load_dotenv(ROOT_DIR / ".env.local")

SUPABASE_URL = os.getenv("VITE_SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("Missing Supabase credentials.")
    sys.exit(1)

def run_dedupe():
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    
    print("Fetching email_queue from Supabase...")
    # Fetch all records without mutating
    response = requests.get(f"{SUPABASE_URL}/rest/v1/email_queue?status=eq.qued", headers=headers)
    
    if response.status_code != 200:
        print(f"Error fetching: {response.text}")
        return
        
    qued = response.json()
    print(f"\n--- DEDUPLICATION OF email_queue ---")
    print(f"Total 'qued' rows fetched: {len(qued)}")
    
    if not qued:
        print("No 'qued' rows found.")
        return
        
    unique_recipients = {}
    
    for r in qued:
        raw_email = r.get("recipient_email") or ""
        email = raw_email.lower().strip()
            
        if email not in unique_recipients:
            unique_recipients[email] = []
        unique_recipients[email].append(r)
    
    duplicate_groups = {email: rows for email, rows in unique_recipients.items() if len(rows) > 1}
    
    if not duplicate_groups:
        print("No duplicates found. Queue is clean.")
        return
        
    print(f"Found {len(duplicate_groups)} unique emails with duplicates.")
    
    to_mark_duplicate = []
    
    for email, rows in duplicate_groups.items():
        def sort_key(row):
            is_test = 1 if "test" in (row.get("recipient_email") or "").lower() else 0
            created = row.get("created_at") or "9999"
            row_id = row.get("id") or 0
            return (is_test, created, row_id)
            
        sorted_rows = sorted(rows, key=sort_key)
        retained = sorted_rows[0]
        duplicates = sorted_rows[1:]
        
        for d in duplicates:
            to_mark_duplicate.append({
                "id": d["id"],
                "original_status": d["status"],
                "recipient_email": email
            })
            
    print(f"Identified {len(to_mark_duplicate)} duplicate rows to be muted.")
    
    # Create backup artifact
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BASE_DIR / f"dedupe_backup_{timestamp}.json"
    with open(backup_path, "w") as f:
        json.dump(to_mark_duplicate, f, indent=2)
    print(f"Backup created at: {backup_path}")
    
    # Mutate
    print("Mutating duplicates to 'duplicate' status...")
    mutated_count = 0
    for dup in to_mark_duplicate:
        row_id = dup["id"]
        payload = {"status": "duplicate", "updated_at": datetime.now().isoformat()}
        res = requests.patch(f"{SUPABASE_URL}/rest/v1/email_queue?id=eq.{row_id}", headers=headers, json=payload)
        if res.status_code in (200, 204):
            mutated_count += 1
        else:
            print(f"Failed to update row {row_id}: {res.text}")
            
    print(f"\nSuccessfully muted {mutated_count} duplicate rows.")
    
    # Re-verify
    res_verify = requests.get(f"{SUPABASE_URL}/rest/v1/email_queue?status=eq.qued", headers=headers)
    qued_after = res_verify.json()
    
    unique_after = set()
    for r in qued_after:
        email = (r.get("recipient_email") or "").lower().strip()
        unique_after.add(email)
        
    print(f"\n--- VERIFICATION ---")
    print(f"Queued row count after dedupe: {len(qued_after)}")
    print(f"Unique queued recipients: {len(unique_after)}")
    
    if len(qued_after) == len(unique_after):
        print("Deduplication successful. Duplicate queued recipients = 0.")
    else:
        print("WARNING: Queue still contains duplicates.")

if __name__ == "__main__":
    run_dedupe()
