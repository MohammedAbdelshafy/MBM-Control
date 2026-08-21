"""
NPI Registry + Google Maps Lead Verifier
=========================================
Verifies dialer leads using:
  1. CMS NPI Registry API (free, official) — confirms provider name + phone
  2. RapidAPI Local Business Data (Google Maps) — cross-references business phone

These leads came FROM the NPI registry, so verification is a direct round-trip.
"""
import json, os, re, sys, io, time, requests
from pathlib import Path
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

DB_PATH = Path(r"C:\Users\omare\OneDrive\Desktop\AI\mbm-dialer\app\public\leads_database.json")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "").strip()

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from MBM.GLM.single_writer_lock import DialerSingleWriter
    _SINGLE_WRITER = DialerSingleWriter()
except Exception:
    _SINGLE_WRITER = None

# CMS NPI Registry — free, no API key
NPI_API = "https://npiregistry.cms.hhs.gov/api/"

# RapidAPI Local Business Data (Google Maps)
GMAPS_API = "https://local-business-data.p.rapidapi.com/search"
GMAPS_HEADERS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": "local-business-data.p.rapidapi.com"
}

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
DELAY = 0.5  # NPI is generous with rate limits


def normalize_phone(phone):
    if not phone:
        return ""
    return re.sub(r"\D", "", str(phone))[-10:]


def query_npi_by_name(name, state=""):
    """Search NPI registry by provider name."""
    if not name or len(name.strip()) < 3:
        return []
    
    parts = name.strip().split()
    params = {"version": "2.1", "limit": 5}
    
    # Try organization name first (clinics)
    params["organization_name"] = name
    if state:
        params["state"] = state
    
    try:
        resp = requests.get(NPI_API, params=params, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            if results:
                return results
    except Exception:
        pass
    
    # Try individual name (first + last)
    if len(parts) >= 2:
        params2 = {
            "version": "2.1",
            "first_name": parts[0],
            "last_name": parts[-1],
            "limit": 5
        }
        if state:
            params2["state"] = state
        try:
            resp = requests.get(NPI_API, params=params2, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("results", [])
        except Exception:
            pass
    
    return []


def query_npi_by_phone(phone):
    """Search NPI registry by phone number."""
    phone_10 = normalize_phone(phone)
    if len(phone_10) != 10:
        return []
    
    # NPI API doesn't support direct phone search, but we can use
    # the enumeration_type filter with phone in the taxonomy
    # Actually, let's try the number field for NPI number lookup
    return []


def extract_npi_phone(result):
    """Extract phone from NPI result."""
    addresses = result.get("addresses", [])
    for addr in addresses:
        phone = addr.get("telephone_number", "")
        if phone:
            return phone
    return ""


def extract_npi_name(result):
    """Extract name from NPI result."""
    basic = result.get("basic", {})
    # Organization
    org = basic.get("organization_name", "")
    if org:
        return org
    # Individual
    first = basic.get("first_name", "")
    last = basic.get("last_name", "")
    if first and last:
        return f"{first} {last}"
    return ""


def query_google_maps(business_name, phone=""):
    """Search Google Maps for a business to verify phone."""
    query = business_name
    if phone:
        query += f" {phone}"
    
    try:
        resp = requests.get(
            GMAPS_API,
            headers=GMAPS_HEADERS,
            params={"query": query, "limit": 3},
            timeout=10
        )
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("data", [])
            if results:
                return results
    except Exception:
        pass
    return []


def extract_state_from_phone(phone):
    """Guess state from area code (rough mapping for top codes)."""
    area_code_map = {
        "210": "TX", "214": "TX", "254": "TX", "281": "TX", "512": "TX",
        "713": "TX", "817": "TX", "832": "TX", "903": "TX", "956": "TX",
        "212": "NY", "315": "NY", "347": "NY", "516": "NY", "518": "NY",
        "607": "NY", "631": "NY", "646": "NY", "716": "NY", "718": "NY",
        "917": "NY", "929": "NY",
        "213": "CA", "310": "CA", "323": "CA", "408": "CA", "415": "CA",
        "510": "CA", "619": "CA", "626": "CA", "650": "CA", "707": "CA",
        "714": "CA", "760": "CA", "805": "CA", "818": "CA", "858": "CA",
        "909": "CA", "916": "CA", "925": "CA", "949": "CA", "951": "CA",
        "305": "FL", "321": "FL", "352": "FL", "386": "FL", "407": "FL",
        "561": "FL", "727": "FL", "772": "FL", "786": "FL", "813": "FL",
        "850": "FL", "863": "FL", "904": "FL", "941": "FL", "954": "FL",
        "178": "PR", "787": "PR", "939": "PR",
        "208": "ID", "312": "IL", "773": "IL",
    }
    digits = normalize_phone(phone)
    if len(digits) >= 10:
        ac = digits[:3] if len(digits) == 10 else digits[1:4]
        return area_code_map.get(ac, "")
    return ""


def main():
    with open(DB_PATH, "r", encoding="utf-8") as f:
        leads = json.load(f)

    total = len(leads)
    print("=" * 70)
    print("  NPI REGISTRY + GOOGLE MAPS LEAD VERIFIER")
    print("=" * 70)
    print(f"  Total leads: {total}")
    print(f"  Batch size: {BATCH_SIZE}")
    print(f"  Source 1: CMS NPI Registry (npiregistry.cms.hhs.gov)")
    print(f"  Source 2: Google Maps (local-business-data.p.rapidapi.com)")
    print("=" * 70)

    verified = 0
    enriched = 0
    unverified = 0
    already_done = 0
    processed = 0
    gmaps_verified = 0

    for i, lead in enumerate(leads):
        if lead.get("skip_trace_status") == "VERIFIED":
            already_done += 1
            continue

        if processed >= BATCH_SIZE:
            break

        processed += 1
        contact = lead.get("contact", "")
        phone = lead.get("phone", "")
        phone_norm = normalize_phone(phone)
        npi_number = lead.get("details", {}).get("NPI", "")
        vertical = lead.get("vertical", "")
        company = lead.get("company", "")
        
        ts = datetime.now().strftime("%H:%M:%S")
        state = extract_state_from_phone(phone)

        # ------- Source 1: NPI Registry -------
        search_name = company if company else contact
        npi_results = query_npi_by_name(search_name, state)
        time.sleep(DELAY)

        npi_matched = False
        for npi_res in npi_results:
            npi_phone = normalize_phone(extract_npi_phone(npi_res))
            npi_name = extract_npi_name(npi_res)

            if npi_phone and phone_norm and npi_phone == phone_norm:
                lead["skip_trace_status"] = "VERIFIED"
                lead["skip_trace_source"] = "CMS NPI Registry"
                lead["skip_trace_confidence"] = "high"
                lead["skip_trace_npi_name"] = npi_name
                npi_number_found = npi_res.get("number", "")
                if npi_number_found:
                    lead["npi_number"] = npi_number_found
                verified += 1
                print(f"  [{ts}] [{i+1}/{total}] [OK] VERIFIED (NPI): {contact} | {phone} | NPI: {npi_number_found}")
                npi_matched = True
                break

        if npi_matched:
            continue

        # If NPI found data but different phone, enrich
        if npi_results:
            npi_res = npi_results[0]
            npi_phone = normalize_phone(extract_npi_phone(npi_res))
            npi_name = extract_npi_name(npi_res)
            if npi_phone or npi_name:
                lead["skip_trace_status"] = "ENRICHED"
                lead["skip_trace_source"] = "CMS NPI Registry"
                lead["skip_trace_confidence"] = "medium"
                if npi_phone and npi_phone != phone_norm:
                    lead["skip_trace_phone_alt"] = npi_phone
                if npi_name:
                    lead["skip_trace_npi_name"] = npi_name
                npi_number_found = npi_res.get("number", "")
                if npi_number_found:
                    lead["npi_number"] = npi_number_found
                enriched += 1
                print(f"  [{ts}] [{i+1}/{total}] [+] ENRICHED (NPI): {contact} | alt: {npi_phone} | {npi_name}")
                continue

        # ------- Source 2: Google Maps -------
        gmaps_results = query_google_maps(search_name, phone)
        time.sleep(DELAY)

        gmaps_matched = False
        for gres in gmaps_results:
            gphone = normalize_phone(gres.get("phone_number", ""))
            gname = gres.get("name", "")

            if gphone and phone_norm and gphone == phone_norm:
                lead["skip_trace_status"] = "VERIFIED"
                lead["skip_trace_source"] = "Google Maps"
                lead["skip_trace_confidence"] = "high"
                lead["skip_trace_gmaps_name"] = gname
                lead["skip_trace_gmaps_address"] = gres.get("full_address", "")
                verified += 1
                gmaps_verified += 1
                print(f"  [{ts}] [{i+1}/{total}] [OK] VERIFIED (GMaps): {contact} | {phone} | {gname}")
                gmaps_matched = True
                break

        if gmaps_matched:
            continue

        if gmaps_results:
            gres = gmaps_results[0]
            gphone = normalize_phone(gres.get("phone_number", ""))
            gname = gres.get("name", "")
            if gphone or gname:
                lead["skip_trace_status"] = "ENRICHED"
                lead["skip_trace_source"] = "Google Maps"
                lead["skip_trace_confidence"] = "medium"
                if gphone and gphone != phone_norm:
                    lead["skip_trace_phone_alt"] = gphone
                if gname:
                    lead["skip_trace_gmaps_name"] = gname
                lead["skip_trace_gmaps_address"] = gres.get("full_address", "")
                enriched += 1
                print(f"  [{ts}] [{i+1}/{total}] [+] ENRICHED (GMaps): {contact} | {gname}")
                continue

        # Neither source confirmed
        lead["skip_trace_status"] = "UNVERIFIED"
        unverified += 1
        print(f"  [{ts}] [{i+1}/{total}] [X] UNVERIFIED: {contact} | {phone}")

    # Save
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from MBM.LeadEngine.dialer_gateway import commit_dialer_db
    commit_dialer_db(leads, reason="npi_gmaps_verifier", author="NPI_GMAPS_VERIFIER")

    remaining = total - already_done - processed
    print()
    print("=" * 70)
    print("  NPI + GOOGLE MAPS VERIFICATION -- BATCH COMPLETE")
    print("=" * 70)
    print(f"  Processed this batch  : {processed}")
    print(f"  Already verified      : {already_done}")
    print(f"  [OK] VERIFIED (NPI)   : {verified - gmaps_verified}")
    print(f"  [OK] VERIFIED (GMaps) : {gmaps_verified}")
    print(f"  [+]  ENRICHED         : {enriched}")
    print(f"  [X]  UNVERIFIED       : {unverified}")
    print(f"  Remaining to process  : {remaining}")
    print("=" * 70)
    print(f"\n  Re-run to process the next {BATCH_SIZE} leads.")

if __name__ == "__main__":
    main()
