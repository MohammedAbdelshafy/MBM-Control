#!/usr/bin/env python3
import sys
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.dialer_db_lock import DialerDatabaseLock

def monitor():
    with DialerDatabaseLock() as lock:
        db = lock.read()
    
    wedding_leads = [d for d in db if d.get("campaign") == "WEDDINGS_AI_REVENUE_US"]
    
    if not wedding_leads:
        print("No leads found for WEDDINGS_AI_REVENUE_US campaign.")
        return
    
    status_counts = {}
    for lead in wedding_leads:
        status = lead.get("status", "UNKNOWN")
        status_counts[status] = status_counts.get(status, 0) + 1
        
    print(f"--- WEDDINGS CAMPAIGN MONITOR ---")
    print(f"Total Leads: {len(wedding_leads)}")
    for status, count in status_counts.items():
        print(f" - {status}: {count}")

if __name__ == "__main__":
    monitor()
