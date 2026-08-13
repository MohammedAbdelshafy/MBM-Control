import os
import csv
import sys
import glob

# Ensure LeadEngine is in path for imports if needed
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'LeadEngine'))
from contact_enrichment import ContactEnricher

def clean_phone(phone):
    if not phone:
        return ""
    # Keep only digits and plus
    cleaned = ''.join(c for c in str(phone) if c.isdigit() or c == '+')
    if len(cleaned) < 10:
        return ""
    if not cleaned.startswith('+1') and len(cleaned) == 10:
        cleaned = '+1' + cleaned
    return cleaned

def aggregate_and_verify():
    artifacts_dir = os.path.join(os.path.dirname(__file__), '..', 'Artifacts')
    csv_files = glob.glob(os.path.join(artifacts_dir, '*.csv'))
    
    unique_contacts = {} # phone -> dict with info
    enricher = ContactEnricher()
    
    # Files that are already verified
    verified_files = ['npi_verified_callsheet.csv', 'wholesalers_final_qualified.csv', 'Final_Qualified_Leads.csv', 'buyer_contacts.csv', 'distressed_sellers.csv']
    
    for fpath in csv_files:
        fname = os.path.basename(fpath)
        is_verified_source = fname in verified_files
        
        try:
            with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                reader = csv.DictReader(f)
                headers = [h.strip().lower() for h in reader.fieldnames] if reader.fieldnames else []
                
                # Guess column mappings
                phone_cols = [c for c in headers if 'phone' in c or 'mobile' in c]
                name_cols = [c for c in headers if c in ['name', 'contact', 'contact_name', 'agent_name', 'agent', 'full name', 'owner name']]
                company_cols = [c for c in headers if c in ['company', 'business', 'organization', 'agency', 'provider_organization_name', 'provider_first_name']]
                city_cols = [c for c in headers if c in ['city', 'location', 'market', 'provider_business_mailing_address_city_name']]
                
                if not phone_cols:
                    continue
                
                phone_col = phone_cols[0]
                name_col = name_cols[0] if name_cols else None
                company_col = company_cols[0] if company_cols else None
                city_col = city_cols[0] if city_cols else None
                
                for row in reader:
                    # Map to lowercase keys to match our guessed columns
                    lower_row = {k.strip().lower(): v for k, v in row.items() if k}
                    
                    raw_phone = lower_row.get(phone_col, '')
                    phone = clean_phone(raw_phone)
                    
                    if not phone:
                        continue
                        
                    name = lower_row.get(name_col, '') if name_col else ''
                    company = lower_row.get(company_col, '') if company_col else ''
                    city = lower_row.get(city_col, '') if city_col else ''
                    
                    display_name = company or name or "Unknown Entity"
                    if display_name == "Unknown Entity" and 'provider_first_name' in lower_row and 'provider_last_name_legal_name' in lower_row:
                         display_name = f"{lower_row['provider_first_name']} {lower_row['provider_last_name_legal_name']}"
                    
                    # Deduplicate by phone
                    if phone not in unique_contacts:
                        unique_contacts[phone] = {
                            'Phone': phone,
                            'Company/Name': display_name,
                            'City': city,
                            'Source': fname,
                            'Verified': is_verified_source
                        }
                    else:
                        # If we found it in a verified source, upgrade its status
                        if is_verified_source:
                            unique_contacts[phone]['Verified'] = True
                            
        except Exception as e:
            print(f"Error reading {fname}: {e}")
            
    # Now let's try to verify a subset of unverified contacts using ContactEnricher
    # We will limit API calls to 50 to avoid blowing through quota on this single run
    unverified = [v for v in unique_contacts.values() if not v['Verified']]
    print(f"Total Unique Numbers: {len(unique_contacts)}")
    print(f"Verified from source: {len(unique_contacts) - len(unverified)}")
    print(f"Unverified: {len(unverified)}. Running skip trace on top 50 unverified...")
    
    traced_count = 0
    for contact in unverified:
        if traced_count >= 0:
            break
            
        if not contact['Company/Name'] or contact['Company/Name'] == "Unknown Entity":
            continue
            
        try:
            # We use search_agency_email just to trigger the API, it also returns phone if found
            res = enricher.search_agency_email(contact['Company/Name'], contact['City'] or 'USA')
            if isinstance(res, dict) and res.get('phone'):
                contact['Verified'] = True
                traced_count += 1
                print(f"Verified via Skip Trace: {contact['Company/Name']} - {res['phone']}")
        except Exception as e:
            pass
            
    output_path = os.path.join(artifacts_dir, 'all_verified_numbers.csv')
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['Phone', 'Company/Name', 'City', 'Source', 'Verified'])
        writer.writeheader()
        
        # Write only verified numbers + the newly traced ones
        for phone, info in unique_contacts.items():
            if info['Verified']:
                writer.writerow(info)
                
    print(f"Saved {sum(1 for i in unique_contacts.values() if i['Verified'])} verified numbers to {output_path}")

if __name__ == "__main__":
    aggregate_and_verify()
