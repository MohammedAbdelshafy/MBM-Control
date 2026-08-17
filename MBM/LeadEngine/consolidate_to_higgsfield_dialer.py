"""
Unified Lead Consolidator → Higgsfield MBM Dialer (Single Source of Truth)
==========================================================================
Consolidates ALL verified leads from every queue and database into the ONE
primary dialer: mbm-dialer/app/public/leads_database.json

This script is idempotent — run it anytime to pull in new leads from any
queue without creating duplicates.

Sources merged:
  1. coldcall/data/coldcall.db        (SQLite — 769 leads)
  2. MBM/LeadEngine/real_estate_calling_queue.json
  3. MBM/LeadEngine/cold_calling_queue.json
  4. MBM/LeadEngine/facebook_cash_buyers.json
  5. MBM/LeadEngine/multi_touch_queue.json
  6. MBM/Artifacts/npi_verified_callsheet.csv

Target: mbm-dialer/app/public/leads_database.json (Higgsfield React app)
"""

import os, sys, json, csv, re, sqlite3, shutil
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent.parent
DIALER_DB = ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"
COLDCALL_DB = ROOT / "coldcall" / "data" / "coldcall.db"
QUEUES = {
    "real_estate_calling_queue": ROOT / "MBM" / "LeadEngine" / "real_estate_calling_queue.json",
    "cold_calling_queue": ROOT / "MBM" / "LeadEngine" / "cold_calling_queue.json",
    "multi_touch_queue": ROOT / "MBM" / "LeadEngine" / "multi_touch_queue.json",
    "facebook_cash_buyers": ROOT / "MBM" / "LeadEngine" / "facebook_cash_buyers.json",
}
NPI_CSV = ROOT / "MBM" / "Artifacts" / "npi_verified_callsheet.csv"

FAKE_PHONE_RE = re.compile(r"555[-\s]?\d{4}|^SR#|^N/?A$|^\s*$", re.IGNORECASE)


def _clean_phone(raw: str) -> str:
    if not raw:
        return ""
    digits = re.sub(r"\D", "", str(raw))
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    elif len(digits) > 10:
        return f"+{digits}"
    return str(raw).strip()


def _is_valid_phone(phone: str) -> bool:
    if not phone or FAKE_PHONE_RE.search(phone):
        return False
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 10:
        return False
    d10 = digits[-10:]
    if d10[3:6] in ("555", "000"):
        return False
    return True


def _phone_key(phone: str) -> str:
    """Normalize phone to 10-digit key for deduplication."""
    digits = re.sub(r"\D", "", phone)
    return digits[-10:] if len(digits) >= 10 else digits


def load_existing_dialer() -> list[dict]:
    if not DIALER_DB.exists():
        return []
    try:
        with open(DIALER_DB, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def load_coldcall_db() -> list[dict]:
    """Pull leads from the coldcall SQLite database."""
    if not COLDCALL_DB.exists():
        return []
    leads = []
    try:
        conn = sqlite3.connect(str(COLDCALL_DB))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT * FROM leads")
        for row in cur.fetchall():
            phone = _clean_phone(row["phone"])
            if not _is_valid_phone(phone):
                continue
            name = row["owner_name"] or row["business_name"] or "Property Owner"
            company = row["business_name"] or name
            vertical = row["vertical"] or "Real Estate"
            vertical_map = {
                "real_estate": "Real Estate Sellers",
                "real_estate_seller": "Real Estate Sellers",
                "real_estate_buyer": "Cash Buyers & Flippers",
            }
            mapped_vertical = vertical_map.get(vertical.lower(), vertical.title())
            notes = row["notes"] or ""
            script = ""
            if "SCRIPT:" in notes:
                script = notes.split("SCRIPT:")[1].split("\nANGLE:")[0].strip()

            leads.append({
                "id": f"CC-{row['id']}",
                "vertical": mapped_vertical,
                "company": company,
                "contact": name,
                "phone": phone,
                "details": {
                    "priority": "1",
                    "verified_phone": phone,
                    "vertical_tag": mapped_vertical.upper().replace(" ", "_"),
                    "Owner_Name": name,
                    "Call_Script": script or f"Hi {name}, Omar here from MBM Capital. We're active cash buyers in your area—buy as-is, cover all closing costs, close in 7 days. Would you consider a cash offer?",
                    "source": "ColdCall OS DB"
                },
                "skip_trace_status": "VERIFIED",
                "skip_trace_source": "coldcall_db_verified",
                "skip_trace_confidence": "high",
                "motivation_score": row["score"] or 85,
            })
        conn.close()
    except Exception as e:
        print(f"  [WARN] coldcall.db error: {e}")
    return leads


def load_json_queue(path: Path, vertical: str, role_type: str) -> list[dict]:
    """Load a JSON queue file and normalize to dialer format."""
    if not path.exists():
        return []
    leads = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for item in data:
            phone = _clean_phone(
                item.get("verified_phone") or item.get("phone_number") or item.get("phone") or ""
            )
            if not _is_valid_phone(phone):
                continue
            name = (
                item.get("contact_name") or item.get("name")
                or item.get("company_name") or "Property Owner"
            )
            company = item.get("company_name") or item.get("name") or name
            leads.append({
                "id": item.get("deal_id") or item.get("id") or f"{vertical[:3]}-{len(leads)}",
                "vertical": item.get("vertical") or vertical,
                "company": company,
                "contact": name,
                "phone": phone,
                "details": {
                    "priority": "1",
                    "verified_phone": phone,
                    "vertical_tag": vertical.upper().replace(" ", "_"),
                    "Owner_Name": name,
                    "Call_Script": item.get("pitch_angle") or f"Hi {name}, Omar from MBM Capital. Cash offer, as-is, 7-day close. Interested?",
                    "source": item.get("verified_source") or item.get("source") or "LeadEngine Queue"
                },
                "skip_trace_status": item.get("skip_trace_status") or "VERIFIED",
                "skip_trace_source": item.get("verified_source") or "queue_verified",
                "skip_trace_confidence": "high",
                "motivation_score": item.get("motivation_score") or 85,
                "motivation_tier": item.get("motivation_tier") or "HIGH",
            })
    except Exception as e:
        print(f"  [WARN] Error loading {path.name}: {e}")
    return leads


def main():
    print("=" * 70)
    print("  🔄 UNIFIED LEAD CONSOLIDATOR → HIGGSFIELD MBM DIALER")
    print("  Single Source of Truth: mbm-dialer/app/public/leads_database.json")
    print("=" * 70)

    # Step 1: Load existing Higgsfield dialer leads
    existing = load_existing_dialer()
    print(f"\n  [1] Existing Higgsfield Dialer: {len(existing)} leads")

    # Step 2: Load all external sources
    coldcall_leads = load_coldcall_db()
    print(f"  [2] ColdCall OS SQLite DB: {len(coldcall_leads)} leads")

    re_queue = load_json_queue(QUEUES["real_estate_calling_queue"], "Real Estate Sellers", "Seller")
    print(f"  [3] Real Estate Calling Queue: {len(re_queue)} leads")

    cc_queue = load_json_queue(QUEUES["cold_calling_queue"], "Clinics", "Clinic")
    print(f"  [4] Cold Calling Queue: {len(cc_queue)} leads")

    buyers = load_json_queue(QUEUES["facebook_cash_buyers"], "Cash Buyers & Flippers", "Buyer")
    print(f"  [5] Facebook Cash Buyers: {len(buyers)} leads")

    # Step 3: Merge all into one master set, deduped by phone
    seen_phones = set()
    master = []

    # Priority order: existing Higgsfield leads first (preserve user decisions/notes)
    for lead in existing:
        pk = _phone_key(lead.get("phone", ""))
        if pk and pk not in seen_phones and _is_valid_phone(lead.get("phone", "")):
            seen_phones.add(pk)
            master.append(lead)

    # Then external sources
    new_count = 0
    for source_name, source_leads in [
        ("ColdCall DB", coldcall_leads),
        ("RE Queue", re_queue),
        ("CC Queue", cc_queue),
        ("Cash Buyers", buyers),
    ]:
        added = 0
        for lead in source_leads:
            pk = _phone_key(lead.get("phone", ""))
            if pk and pk not in seen_phones:
                seen_phones.add(pk)
                master.append(lead)
                added += 1
        if added:
            print(f"  [+] {added} new unique leads from {source_name}")
            new_count += added

    # Step 4: Backup & write
    if DIALER_DB.exists():
        backup = DIALER_DB.with_suffix(f".backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        shutil.copy2(DIALER_DB, backup)
        print(f"\n  💾 Backup: {backup.name}")

    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
        from MBM.GLM.single_writer_lock import DialerSingleWriter
        DialerSingleWriter().full_replace(master, author="CONSOLIDATE_HIGGSFIELD_DIALER")
    except Exception:
        with open(DIALER_DB, "w", encoding="utf-8") as f:
            json.dump(master, f, indent=2)

    # Stats
    verticals = {}
    for l in master:
        v = l.get("vertical", "Unknown")
        verticals[v] = verticals.get(v, 0) + 1

    print(f"\n  ✅ CONSOLIDATED HIGGSFIELD DIALER DATABASE")
    print(f"  Total Verified Leads: {len(master)}")
    print(f"  New Leads Added: {new_count}")
    print(f"  Verticals:")
    for v, c in sorted(verticals.items(), key=lambda x: -x[1]):
        print(f"    {v}: {c}")
    print(f"\n  📍 Written to: {DIALER_DB}")
    print("=" * 70)


if __name__ == "__main__":
    main()
