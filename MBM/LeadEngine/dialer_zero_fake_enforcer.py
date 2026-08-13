"""
Dialer Zero-Fake-Data Enforcer
==============================
Scans leads_database.json and REMOVES any lead that lacks:
  1. A real person name (not placeholder / generic)
  2. A real dialable phone number (not 555, not SR#, not N/A)

Only leads with BOTH a name and phone survive.
"""
import json, re, sys
from pathlib import Path

DB = Path(r"C:\Users\omare\OneDrive\Desktop\AI\mbm-dialer\app\public\leads_database.json")

FAKE_NAME_MARKERS = [
    "Action_Required", "Skip_Trace", "Unknown", "N/A", "Distressed Seller",
    "Property Owner", "Hedge Fund", "Cash Buyer", "Acquisition Group",
    "TBD", "PENDING", "placeholder", "test", "demo",
]

FAKE_PHONE_PATTERNS = re.compile(
    r"(555[-\s]?\d{4})"           # 555 numbers
    r"|(^SR#)"                     # service request IDs
    r"|(^N/?A$)"                   # N/A
    r"|(^\s*$)"                    # blank
    r"|(\+1\s?\(\d{3}\)\s?555)"   # +1 (xxx) 555
, re.IGNORECASE)

def is_real_name(name: str) -> bool:
    if not name or len(name.strip()) < 3:
        return False
    for marker in FAKE_NAME_MARKERS:
        if marker.lower() in name.lower():
            return False
    # Must have at least two words (first + last name)
    parts = name.strip().split()
    if len(parts) < 2:
        return False
    return True

def is_real_phone(phone: str) -> bool:
    if not phone or len(phone.strip()) < 7:
        return False
    if FAKE_PHONE_PATTERNS.search(phone):
        return False
    # Must have at least 10 digits
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 10:
        return False
    return True

def main():
    with open(DB, "r", encoding="utf-8") as f:
        leads = json.load(f)

    total = len(leads)
    kept = []
    removed_no_name = 0
    removed_no_phone = 0
    removed_both = 0

    for lead in leads:
        contact = lead.get("contact", "")
        phone = lead.get("phone", "")

        has_name = is_real_name(contact)
        has_phone = is_real_phone(phone)

        if has_name and has_phone:
            kept.append(lead)
        elif not has_name and not has_phone:
            removed_both += 1
        elif not has_name:
            removed_no_name += 1
        else:
            removed_no_phone += 1

    removed_total = total - len(kept)

    print("=" * 60)
    print("  DIALER ZERO-FAKE-DATA ENFORCER REPORT")
    print("=" * 60)
    print(f"  Total leads scanned   : {total}")
    print(f"  Leads with name+phone : {len(kept)} (KEPT)")
    print(f"  Removed (no name)     : {removed_no_name}")
    print(f"  Removed (no phone)    : {removed_no_phone}")
    print(f"  Removed (both missing): {removed_both}")
    print(f"  TOTAL REMOVED         : {removed_total}")
    print("=" * 60)

    # Show sample of kept leads
    print("\n--- SAMPLE VERIFIED LEADS (first 10) ---")
    for lead in kept[:10]:
        print(f"  {lead.get('contact','?'):<30} | {lead.get('phone','?'):<18} | {lead.get('vertical','?')}")

    # Save cleaned database
    with open(DB, "w", encoding="utf-8") as f:
        json.dump(kept, f, indent=2, default=str)

    print(f"\n[DONE] Saved {len(kept)} verified leads to leads_database.json")
    print(f"[DONE] Purged {removed_total} entries without real name + real phone.")

if __name__ == "__main__":
    main()
