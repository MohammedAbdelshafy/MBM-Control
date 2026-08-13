import json
import os
import sys
from free_skip_tracer import FreeSkipTracer

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "mbm-dialer", "app", "public", "leads_database.json")

def run_ensurement():
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found.")
        return

    with open(DB_PATH, 'r', encoding='utf-8') as f:
        db = json.load(f)

    tracer = FreeSkipTracer()
    
    print(f"Loaded {len(db)} leads.")
    
    # We will only keep leads that have valid phone numbers.
    # For sellers or leads with fake numbers (555), we enforce skip tracing.
    
    verified_db = []
    
    sellers = [l for l in db if l.get('vertical') == 'Real Estate Sellers']
    print(f"Found {len(sellers)} Real Estate Sellers. Applying Skip Trace Ensurement...")
    
    for i, lead in enumerate(db):
        vertical = lead.get('vertical')
        phone = lead.get('phone', '')
        name = lead.get('contact', '')
        address = lead.get('details', {}).get('Address') or lead.get('details', {}).get('Property_Address', '')
        city = lead.get('details', {}).get('City', '')
        
        # Check if it needs skip tracing
        needs_skiptrace = False
        if vertical == 'Real Estate Sellers':
            needs_skiptrace = True
        elif '555' in phone or phone == '' or 'ACTION_REQUIRED' in phone or phone == 'No Number Found':
            needs_skiptrace = True
            
        if not needs_skiptrace:
            verified_db.append(lead)
            continue
            
        # Perform skip trace
        print(f"Skip tracing [{i}/{len(db)}] {name} at {address}...")
        
        # We need a name to skip trace effectively
        if not name or name == 'Property Owner':
            print("  Skipped: No real name provided.")
            continue
            
        result = tracer.find_contact(name=name, address=address, city=city)
        
        if result and result.get("phone"):
            print(f"  SUCCESS! Found real number: {result['phone']} via {result['source']}")
            lead['phone'] = result['phone']
            lead['details']['Owner_Phone'] = result['phone']
            lead['details']['Skip_Trace_Source'] = result['source']
            lead['details']['Skip_Trace_Confidence'] = result['confidence']
            
            # Regenerate the script with the new verified status
            from datetime import datetime
            lead['details']['Verified_Date'] = datetime.now().isoformat()
            
            verified_db.append(lead)
        else:
            print("  FAILED to find real number. Dropping lead from active dialer.")
            
        # Save incrementally every 10 leads to not lose data
        if i % 10 == 0:
            with open(DB_PATH, 'w', encoding='utf-8') as f:
                json.dump(verified_db, f, indent=2)

    # Final save
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(verified_db, f, indent=2)
        
    print(f"\nEnsurement Complete. Kept {len(verified_db)} verified leads with real numbers.")

if __name__ == "__main__":
    run_ensurement()
