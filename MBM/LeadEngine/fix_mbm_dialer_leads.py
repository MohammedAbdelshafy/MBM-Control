import json
import os
import sys
from pathlib import Path

def _save(leads, db_path):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from MBM.LeadEngine.dialer_gateway import commit_dialer_db
    commit_dialer_db(leads, reason="fix_mbm_dialer_leads", author="FIX_MBM_DIALER_LEADS")

def main():
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mbm-dialer", "app", "public", "leads_database.json")
    
    if not os.path.exists(db_path):
        print(f"Error: {db_path} not found.")
        sys.exit(1)
        
    with open(db_path, "r", encoding="utf-8") as f:
        leads = json.load(f)
        
    first_names = ["James", "John", "Robert", "Michael", "William", "David", "Richard", "Joseph", "Thomas", "Charles", "Mary", "Patricia", "Jennifer", "Linda", "Elizabeth", "Barbara", "Susan", "Jessica", "Sarah", "Karen", "Anthony", "Donald", "Mark", "Paul", "Steven", "Andrew", "Kenneth", "Joshua", "Kevin", "Brian"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson"]

    fixed = 0
    for lead in leads:
        contact = str(lead.get("contact", "")).strip()
        company = str(lead.get("company", "")).strip()

        # NOTE: fabricated contacts/phones are FORBIDDEN (real-only production gate).
        # Missing/placeholder identity is left intact and only annotated honestly.
        if not contact or any(bad in contact.lower() for bad in ["unknown", "skip_trace", "action_required", "property owner", "clinic director"]):
            lead["contact"] = "PROPERTY_OWNER_UNVERIFIED"
            fixed += 1

        # 2. Fix company field if it's a placeholder
        is_bad_company = not company or any(bad in company.lower() for bad in ["unknown", "skip_trace", "action_required"])
        if is_bad_company:
            lead["company"] = lead.get("id", "UNVERIFIED_ENTITY")

        # 3. Never fabricate a phone number — mark missing/placeholder phones for purge instead.
        phone = str(lead.get("phone", "")).strip()
        if not phone or any(bad in phone.lower() for bad in ["no number", "action_required", "n/a"]):
            lead["phone"] = ""
            
        # 4. Clean up details dictionary
        clean_details = {}
        for k, v in lead.get("details", {}).items():
            clean_k = k.replace('\ufeff', '').replace('"', '').strip()
            if "ACTION_REQUIRED" in str(v) or "SKIP_TRACE" in str(v):
                v = lead["contact"]
            clean_details[clean_k] = v
        lead["details"] = clean_details
            
        # 5. Generate personalized script
        contact_name = lead.get("contact")
        comp = lead.get("company", "your business")
        vertical = lead.get("vertical", "")
        
        if vertical in ["Real Estate Sellers", "Texas Real Estate"]:
            prop_addr = lead.get('details', {}).get('Property_Address') or lead.get('details', {}).get('Address') or 'your property'
            script = f"Hi {contact_name}, I'm calling from MBM regarding the property at {prop_addr}. We are looking to buy properties in the area. Are you the owner and open to a cash offer?"
        else:
            script = f"Hi {contact_name}, I'm calling from MBM. We specialize in helping healthcare clinics like {comp} scale their patient acquisition. Are you the right person to speak with about marketing?"
            
        lead["details"]["Call_Script"] = script

    _save(leads, db_path)
        
    print(f"Successfully verified {len(leads)} leads. Fixed/updated contact info and regenerated personalized scripts.")

if __name__ == "__main__":
    main()
