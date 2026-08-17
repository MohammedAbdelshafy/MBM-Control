"""
Dialer Skip Trace Verifier (Multi-Source)
==========================================
Uses RapidAPI Skip Tracing + FreeSkipTracer to verify all 7,240 dialer leads.

Sources:
  1. RapidAPI Skip Tracing (skip-tracing-working-api.p.rapidapi.com) — address-based
  2. FreeSkipTracer (TruePeopleSearch, FastPeopleSearch, ZabaSearch, DuckDuckGo) — name-based

Each lead is tagged with:
  skip_trace_status: VERIFIED | ENRICHED | UNVERIFIED
  skip_trace_source: which API confirmed it
  skip_trace_confidence: high | medium | low
"""
import json, os, re, sys, time, requests, io
from pathlib import Path
from datetime import datetime

# Force UTF-8 stdout on Windows to avoid cp1252 encoding crashes
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

sys.path.insert(0, str(Path(__file__).parent.resolve()))

try:
    from dialer_verification_gate import check_lead as gate_check
except Exception:
    gate_check = None

try:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from MBM.GLM.single_writer_lock import DialerSingleWriter
    _writer = DialerSingleWriter()
except Exception as e:
    print(f"[WARN] Single-writer gateway unavailable ({e}); using direct write fallback.")
    _writer = None

DB_PATH = Path(r"C:\Users\omare\OneDrive\Desktop\AI\mbm-dialer\app\public\leads_database.json")
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "572a857767mshe9f183ef86f1060p15ee07jsn900c90701df8")
SKIP_TRACE_URL = "https://skip-tracing-working-api.p.rapidapi.com/search"
SKIP_TRACE_HEADERS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": "skip-tracing-working-api.p.rapidapi.com"
}

BATCH_SIZE = int(os.getenv("BATCH_SIZE", "100"))
DELAY = 1.5  # seconds between API calls

def normalize_phone(phone):
    """Strip to digits only."""
    if not phone:
        return ""
    return re.sub(r"\D", "", str(phone))[-10:]  # last 10 digits

def skip_trace_rapidapi(address):
    """Query RapidAPI skip tracing by address."""
    if not address or len(address.strip()) < 5:
        return None
    try:
        resp = requests.get(
            SKIP_TRACE_URL,
            headers=SKIP_TRACE_HEADERS,
            params={"address": address},
            timeout=15
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict):
                return data
            elif isinstance(data, list) and data:
                return data[0]
        return None
    except Exception:
        return None

def skip_trace_free(name, address=""):
    """Query FreeSkipTracer (local scraper) with timeout protection."""
    try:
        from free_skip_tracer import FreeSkipTracer
        tracer = FreeSkipTracer()
        return tracer.find_contact(name=name, address=address)
    except Exception:
        return {}

def extract_phone_from_skip(data):
    """Pull phone from skip trace result."""
    if not data:
        return ""
    for key in ["phone", "phone_number", "homePhone", "cellPhone", "mobile"]:
        val = data.get(key, "")
        if val:
            return val
    phones = data.get("phones", data.get("phone_numbers", []))
    if isinstance(phones, list) and phones:
        if isinstance(phones[0], dict):
            return phones[0].get("phone", phones[0].get("number", ""))
        return str(phones[0])
    return ""

def extract_name_from_skip(data):
    """Pull owner name from skip trace result."""
    if not data:
        return ""
    for key in ["name", "ownerName", "owner_name", "full_name", "fullName"]:
        val = data.get(key, "")
        if val:
            return val
    first = data.get("firstName", data.get("first_name", ""))
    last = data.get("lastName", data.get("last_name", ""))
    if first and last:
        return f"{first} {last}"
    return ""

def main():
    with open(DB_PATH, "r", encoding="utf-8") as f:
        leads = json.load(f)

    total = len(leads)
    print("=" * 70)
    print("  MULTI-SOURCE SKIP TRACE VERIFICATION ENGINE")
    print("=" * 70)
    print(f"  Total leads: {total}")
    print(f"  Batch size: {BATCH_SIZE}")
    print(f"  Sources: RapidAPI Skip Trace + FreeSkipTracer")
    print("=" * 70)

    verified = 0
    enriched = 0
    unverified = 0
    already_done = 0
    processed = 0

    for i, lead in enumerate(leads):
        # Skip already verified
        if lead.get("skip_trace_status") == "VERIFIED":
            already_done += 1
            continue

        # Skip leads that already pass the dialer verification gate (e.g. NPI
        # clinics verified via details.source/npi_number even though they carry
        # no skip_trace_status). Don't burn API budget re-scraping gate-verified rows.
        if gate_check is not None:
            try:
                if gate_check(lead).get("passed"):
                    already_done += 1
                    continue
            except Exception:
                pass

        if processed >= BATCH_SIZE:
            break

        processed += 1
        contact = lead.get("contact", "")
        phone = lead.get("phone", "")
        phone_norm = normalize_phone(phone)
        details = lead.get("details", {})
        address = ""
        for addr_key in ["Property_Address", "Address", "address", "street_address"]:
            if details.get(addr_key):
                address = details[addr_key]
                break

        ts = datetime.now().strftime("%H:%M:%S")

        # ------- Source 1: RapidAPI Skip Trace (address-based) -------
        skip_data = None
        if address:
            skip_data = skip_trace_rapidapi(address)
            time.sleep(DELAY)

        if skip_data:
            skip_phone = normalize_phone(extract_phone_from_skip(skip_data))
            skip_name = extract_name_from_skip(skip_data)

            if skip_phone and phone_norm and skip_phone == phone_norm:
                lead["skip_trace_status"] = "VERIFIED"
                lead["skip_trace_source"] = "RapidAPI Skip Trace"
                lead["skip_trace_confidence"] = "high"
                if skip_name:
                    lead["skip_trace_owner_name"] = skip_name
                verified += 1
                print(f"  [{ts}] [{i+1}/{total}] [OK] VERIFIED: {contact} | {phone} (RapidAPI match)")
                continue
            elif skip_phone:
                lead["skip_trace_status"] = "ENRICHED"
                lead["skip_trace_phone_alt"] = skip_phone
                lead["skip_trace_source"] = "RapidAPI Skip Trace"
                lead["skip_trace_confidence"] = "medium"
                if skip_name:
                    lead["skip_trace_owner_name"] = skip_name
                enriched += 1
                print(f"  [{ts}] [{i+1}/{total}] [+] ENRICHED: {contact} | alt: {skip_phone} (RapidAPI)")
                continue

        # ------- Source 2: FreeSkipTracer (name-based) -------
        free_result = skip_trace_free(contact, address)
        time.sleep(DELAY)

        if free_result:
            free_phone = normalize_phone(free_result.get("phone", ""))
            free_email = free_result.get("email", "")
            source = free_result.get("source", "FreeSkipTracer")
            confidence = free_result.get("confidence", "low")

            if free_phone and phone_norm and free_phone == phone_norm:
                lead["skip_trace_status"] = "VERIFIED"
                lead["skip_trace_source"] = source
                lead["skip_trace_confidence"] = confidence
                verified += 1
                print(f"  [{ts}] [{i+1}/{total}] [OK] VERIFIED: {contact} | {phone} ({source})")
                continue
            elif free_phone or free_email:
                lead["skip_trace_status"] = "ENRICHED"
                if free_phone:
                    lead["skip_trace_phone_alt"] = free_phone
                if free_email:
                    lead["skip_trace_email"] = free_email
                lead["skip_trace_source"] = source
                lead["skip_trace_confidence"] = confidence
                enriched += 1
                print(f"  [{ts}] [{i+1}/{total}] [+] ENRICHED: {contact} | {free_phone or free_email} ({source})")
                continue

        # Neither source confirmed
        lead["skip_trace_status"] = "UNVERIFIED"
        unverified += 1
        print(f"  [{ts}] [{i+1}/{total}] [X] UNVERIFIED: {contact} | {phone}")

    # Save progress via the canonical single-writer gateway (never raw direct writes)
    if _writer is not None:
        res = _writer.full_replace(leads, author="DIALER_SKIP_TRACE_VERIFIER")
        if not res.get("ok"):
            raise RuntimeError(f"Single-writer commit failed: {res}")
        print(f"[SAVE] Wrote {res['final_count']} leads via single-writer gateway")
    else:
        with open(DB_PATH, "w", encoding="utf-8") as f:
            json.dump(leads, f, indent=2, default=str)

    remaining = total - already_done - processed
    print()
    print("=" * 70)
    print("  SKIP TRACE VERIFICATION -- BATCH COMPLETE")
    print("=" * 70)
    print(f"  Processed this batch  : {processed}")
    print(f"  Already verified      : {already_done}")
    print(f"  [OK] VERIFIED         : {verified}")
    print(f"  [+]  ENRICHED         : {enriched}")
    print(f"  [X]  UNVERIFIED       : {unverified}")
    print(f"  Remaining to process  : {remaining}")
    print("=" * 70)
    print(f"\n  Re-run this script to process the next {BATCH_SIZE} leads.")
    print(f"  Set BATCH_SIZE=500 env var for larger batches.")

if __name__ == "__main__":
    main()
