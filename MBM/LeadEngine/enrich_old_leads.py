import os
import json
import time
from contact_enrichment import ContactEnricher

def enrich_dataset(input_file, output_file):
    if not os.path.exists(input_file):
        print(f"File {input_file} does not exist.")
        return
        
    with open(input_file, 'r', encoding='utf-8') as f:
        leads = json.load(f)
        
    print(f"Enriching {len(leads)} historical leads from {input_file}...")
    enricher = ContactEnricher()
    
    enriched_count = 0
    for lead in leads:
        agent_name = lead.get('agent', 'Unknown Agent')
        address = lead.get('address', 'Unknown City')
        city = address.split(',')[-1].strip() if ',' in address else 'Manchester'
        
        # Skip if already has both phone and email
        existing_phone = lead.get('phone') or lead.get('agent_phone')
        existing_email = lead.get('agent_email')
        if existing_phone and existing_email:
            enriched_count += 1
            continue
            
        # Try ContactEnricher (RapidAPI + DuckDuckGo + Free Skip Tracer)
        result = enricher.search_agency_email(agent_name, city)
        
        if isinstance(result, dict):
            if result.get("email") and not existing_email:
                lead['agent_email'] = result["email"]
                lead['email'] = result["email"]
                enriched_count += 1
            if result.get("phone") and not existing_phone:
                lead['phone'] = result["phone"]
                lead['agent_phone'] = result["phone"]
                enriched_count += 1
        elif isinstance(result, str) and result:
            lead['agent_email'] = result
            lead['email'] = result
            enriched_count += 1
            
        time.sleep(0.5)
        
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(leads, f, indent=2)
        
    print(f"Successfully enriched {enriched_count}/{len(leads)} leads with contact info!")
    print(f"Saved to {output_file}")

if __name__ == "__main__":
    base_dir = os.path.dirname(__file__)
    enrich_dataset(
        os.path.join(base_dir, 'global_leads.json'),
        os.path.join(base_dir, 'enriched_global_leads.json')
    )
