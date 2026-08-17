import csv
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
ARTIFACTS = BASE.parent / "Artifacts"
OUTPUT = BASE.parent.parent / "mbm-dialer" / "app" / "public" / "leads_database.json"

try:
    sys.path.insert(0, str(BASE.parent.parent))
    from MBM.GLM.single_writer_lock import DialerSingleWriter
    _SINGLE_WRITER = DialerSingleWriter()
except Exception:
    _SINGLE_WRITER = None

def load_csv(filename, vertical):
    path = ARTIFACTS / filename
    if not path.exists():
        return []
    leads = []
    with open(path, encoding="utf-8", errors="replace") as f:
        rows = list(csv.DictReader(f))
        for r in rows:
            # Normalize company
            company = (
                r.get("Company") or 
                r.get("company_name") or 
                r.get("company") or 
                r.get("Company Name") or 
                r.get("Entity_Name") or 
                r.get("Property_Address") or 
                r.get("Property Address") or 
                "Unknown"
            )
            
            # Normalize contact
            contact = (
                r.get("Contact_Name") or 
                r.get("contact_name") or 
                r.get("Contact Name") or 
                r.get("authorized_official_name") or 
                r.get("Owner_Name") or 
                r.get("Owner Name")
            )
            
            if not contact and r.get("first_name"):
                contact = (r.get("first_name", "") + " " + r.get("last_name", "")).strip()
            
            if not contact and r.get("Company/Name"):
                contact = r.get("Company/Name")

            if not contact:
                contact = "Unknown"
            phone = r.get("phone") or r.get("Phone") or r.get("Mobile") or ""
            if not phone:
                continue
            
            # Capture all other info
            details = {}
            exclude_keys = ["company_name", "Company Name", "Property Address", "authorized_official_name", "Owner Name", "Contact Name", "phone", "Phone", "Mobile"]
            for k, v in r.items():
                if k and v and k not in exclude_keys:
                    details[k.strip()] = v.strip()

            leads.append({
                "id": f"{vertical}-{len(leads)}",
                "vertical": vertical,
                "company": company.title(),
                "contact": contact.title(),
                "phone": phone,
                "details": details
            })
    return leads

def main():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    all_leads = []
    all_leads.extend(load_csv("npi_verified_callsheet.csv", "Clinics"))
    all_leads.extend(load_csv("master_buyers_list.csv", "Real Estate Buyers"))
    all_leads.extend(load_csv("distressed_sellers.csv", "Real Estate Sellers"))
    
    # Adding all new leads requested by user
    all_leads.extend(load_csv("wholesaler_leads.csv", "Wholesalers"))
    all_leads.extend(load_csv("wholesalers_final_qualified.csv", "Wholesalers Qualified"))
    all_leads.extend(load_csv("real_leads.csv", "Real Leads"))
    all_leads.extend(load_csv("texas_300_leads.csv", "Texas Real Estate"))
    all_leads.extend(load_csv("buyer_contacts.csv", "Buyer Contacts"))
    all_leads.extend(load_csv("all_states_leads.csv", "All States General"))
    all_leads.extend(load_csv("all_leads_master.csv", "Master Catch-All"))
    all_leads.extend(load_csv("all_verified_numbers.csv", "Verified Numbers"))
    
    if _SINGLE_WRITER is not None:
        _SINGLE_WRITER.full_replace(all_leads, author="BUNDLE_DASHBOARD_DATA")
    else:
        with open(OUTPUT, "w", encoding="utf-8") as f:
            json.dump(all_leads, f, indent=2)
    print(f"Bundled {len(all_leads)} leads into {OUTPUT}")

if __name__ == "__main__":
    main()
