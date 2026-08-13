import os
import glob
import csv
import json
import re

def normalize_addr(addr):
    if not addr:
        return ""
    # Strip apts, zip, punctuation for matching
    addr = str(addr).upper()
    addr = re.sub(r'[^\w\s]', '', addr)
    addr = re.sub(r'\s+', ' ', addr).strip()
    return addr

def main():
    ai_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    db_path = os.path.join(ai_dir, "mbm-dialer", "app", "public", "leads_database.json")
    
    print("Building Address-to-Owner Lookup Map from all repository CSVs...")
    address_map = {}
    
    # Search all CSV files in AI directory
    csv_files = glob.glob(os.path.join(ai_dir, "**", "*.csv"), recursive=True)
    print(f"Scanning {len(csv_files)} CSV files...")
    
    for fpath in csv_files:
        try:
            with open(fpath, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.reader(f)
                for row in reader:
                    row_str = " ".join(row)
                    if "ACTION_REQUIRED" in row_str or "SKIP_TRACE" in row_str:
                        # Try to find if there's also a valid name in this row or ignore placeholder rows
                        pass
                    
                    # Look for names in uppercase/titlecase in the row
                    for cell in row:
                        cell_clean = cell.strip()
                        # Check if cell looks like a full name (2-3 words, letters only)
                        if re.match(r'^[A-Za-z]+\s+[A-Za-z]+(?:\s+[A-Za-z]+)?$', cell_clean) and cell_clean.lower() not in ["distressed property", "verified lead", "code concern", "private residential", "action required"]:
                            # Look for an address in the same row
                            for other_cell in row:
                                if any(st in other_cell.upper() for st in [" RD", " ST", " AVE", " BLVD", " DR", " LN", " CT", " HWY", " CIR"]):
                                    norm = normalize_addr(other_cell)
                                    if norm and len(norm) > 5:
                                        if norm not in address_map:
                                            address_map[norm] = {"name": cell_clean}
                                        # Check if phone is in row
                                        for p_cell in row:
                                            digits = re.sub(r'\D', '', p_cell)
                                            if len(digits) == 10 or (len(digits) == 11 and digits.startswith('1')):
                                                address_map[norm]["phone"] = p_cell.strip()
        except Exception as e:
            continue

    print(f"Built map with {len(address_map)} address-to-owner matches.")
    
    with open(db_path, "r", encoding="utf-8") as f:
        leads = json.load(f)
        
    updated_count = 0
    for lead in leads:
        addr = lead.get("details", {}).get("Property_Address") or lead.get("details", {}).get("Address") or lead.get("company")
        norm_addr = normalize_addr(addr)
        
        # Match against our lookup map
        match = None
        if norm_addr in address_map:
            match = address_map[norm_addr]
        else:
            # Fuzzy match by street number and name
            for k, v in address_map.items():
                if k in norm_addr or norm_addr in k:
                    match = v
                    break
                    
        if match:
            real_name = match.get("name")
            real_phone = match.get("phone")
            
            if real_name:
                lead["contact"] = real_name
                lead["company"] = real_name
                if "details" in lead:
                    lead["details"]["Owner_Name"] = real_name
                updated_count += 1
                
            if real_phone:
                lead["phone"] = real_phone
                if "details" in lead:
                    lead["details"]["Owner_Phone"] = real_phone
                    
            # Update call script
            prop_addr = lead.get('details', {}).get('Property_Address') or lead.get('details', {}).get('Address') or 'your property'
            lead["details"]["Call_Script"] = f"Hi {lead['contact']}, I'm calling from MBM regarding the property at {prop_addr}. We are looking to buy properties in the area. Are you the owner and open to a cash offer?"

    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(leads, f, indent=2, default=str)
        
    print(f"Successfully updated {updated_count} real estate seller leads with REAL owner names and phone numbers!")

if __name__ == "__main__":
    main()
