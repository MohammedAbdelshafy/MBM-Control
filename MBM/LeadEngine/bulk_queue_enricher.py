import json
import os
import time
import argparse
from free_skip_tracer import FreeSkipTracer

def load_json(filepath):
    if not os.path.exists(filepath):
        return []
    with open(filepath, 'r') as f:
        return json.load(f)

def save_json(filepath, data):
    with open(filepath, 'w') as f:
        json.dump(data, f, indent=2)

def is_fake_or_missing(phone):
    if not phone:
        return True
    if '555-' in phone or '+1 (555)' in phone or '+1 (214) 555' in phone:
        return True
    return False

def enrich_queue(filepath, is_test=False):
    print(f"--- Processing {os.path.basename(filepath)} ---")
    data = load_json(filepath)
    if not data:
        print("Empty or missing file.")
        return

    tracer = FreeSkipTracer()
    processed = 0
    updated = 0
    
    for idx, lead in enumerate(data):
        if is_test and processed >= 5:
            break
            
        name = lead.get('owner_name') or lead.get('contact_name') or "Unknown Owner"
        address = lead.get('property_address') or lead.get('address') or ""
        city = lead.get('city') or ""
        phone = lead.get('phone')
        
        if is_fake_or_missing(phone) and name != "Unknown Owner" and address:
            print(f"[{idx}] Skip Tracing: {name} at {address} {city}...")
            result = tracer.find_contact(name=name, address=address, city=city)
            processed += 1
            
            if result and result.get('phone'):
                print(f"    -> Found: {result['phone']} (Confidence: {result.get('confidence')})")
                lead['phone'] = result['phone']
                lead['email'] = result.get('email', lead.get('email'))
                lead['skip_trace_confidence'] = result.get('confidence')
                lead['skip_trace_source'] = result.get('source')
                updated += 1
            else:
                print("    -> No highly confident result found.")
                
            time.sleep(1)

    print(f"Enriched {updated} out of {processed} processed leads.")
    if not is_test and updated > 0:
        save_json(filepath, data)
        print("Queue saved.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Run on max 5 leads")
    args = parser.parse_args()
    
    base_dir = os.path.dirname(__file__)
    queues = [
        "distressed_wholesale_leads.json",
        "us_re_dialer_queue.json",
        "cold_calling_queue.json",
        "real_estate_calling_queue.json"
    ]
    
    for q in queues:
        enrich_queue(os.path.join(base_dir, q), is_test=args.test)
