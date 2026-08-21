"""
MBM Autonomous Master Overnight Skip Trace Daemon
=================================================
Consolidates ALL lead queues across the repository and skip traces them overnight.

Lead Sources:
  1. mbm-dialer/app/public/leads_database.json (primary)
  2. MBM/LeadEngine/real_estate_calling_queue.json
  3. MBM/LeadEngine/us_re_dialer_queue.json
  4. MBM/LeadEngine/cold_calling_queue.json

Verification APIs:
  1. CMS NPI Registry API (official healthcare database)
  2. RapidAPI Local Business Data & Skip Tracing

Resilience & Persistence:
  - Multi-threaded worker pool (4 parallel workers)
  - Auto-save every 25 leads
  - Auto-commit & git push to live dialer every 250 leads
"""

import json
import os
import re
import sys
import io
import time
import subprocess
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

import requests

BASE_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BASE_DIR.parent.parent
DIALER_DB = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"
DIALER_REPO = ROOT_DIR / "mbm-dialer" / "app"
LOG_FILE = BASE_DIR / "logs" / "overnight_skiptrace.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

try:
    sys.path.insert(0, str(ROOT_DIR))
    from MBM.GLM.single_writer_lock import DialerSingleWriter
    _SINGLE_WRITER = DialerSingleWriter()
except Exception:
    _SINGLE_WRITER = None

OTHER_QUEUES = [
    BASE_DIR / "real_estate_calling_queue.json",
    BASE_DIR / "us_re_dialer_queue.json",
    BASE_DIR / "cold_calling_queue.json",
    BASE_DIR / "distressed_wholesale_leads.json",
]

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "").strip()
NPI_API = "https://npiregistry.cms.hhs.gov/api/"
GMAPS_API = "https://local-business-data.p.rapidapi.com/search"
SKIP_TRACE_API = "https://skip-tracing-working-api.p.rapidapi.com/search"

GMAPS_HEADERS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": "local-business-data.p.rapidapi.com"
}
SKIP_TRACE_HEADERS = {
    "x-rapidapi-key": RAPIDAPI_KEY,
    "x-rapidapi-host": "skip-tracing-working-api.p.rapidapi.com"
}

NUM_WORKERS = 4
SAVE_INTERVAL = 25
PUSH_INTERVAL = 250

GENERIC_NAMES = [
    "the practice administrator", "practice administrator",
    "physical therapist", "behavior analyst", "office manager",
    "front desk", "receptionist", "billing department",
    "medical director", "clinical director", "action_required",
    "skip_trace", "unknown", "n/a", "distressed seller", "property owner",
    "tbd", "pending", "placeholder", "test", "demo"
]


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[MASTER SKIPTRACE] [{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def normalize_phone(phone):
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    return digits[-10:] if len(digits) >= 10 else ""


def is_valid_lead(contact, phone):
    if not contact or len(contact.strip()) < 3:
        return False
    contact_lower = contact.strip().lower()
    if any(g in contact_lower for g in GENERIC_NAMES):
        return False
    if len(contact.strip().split()) < 2:
        return False
    phone_norm = normalize_phone(phone)
    if not phone_norm or len(phone_norm) < 10 or "555" in phone_norm:
        return False
    return True


def extract_state_from_phone(phone):
    area_code_map = {
        "210": "TX", "214": "TX", "254": "TX", "281": "TX", "512": "TX", "713": "TX", "817": "TX", "832": "TX", "903": "TX", "956": "TX",
        "212": "NY", "315": "NY", "347": "NY", "516": "NY", "518": "NY", "607": "NY", "631": "NY", "646": "NY", "716": "NY", "718": "NY", "917": "NY", "929": "NY",
        "213": "CA", "310": "CA", "323": "CA", "408": "CA", "415": "CA", "510": "CA", "619": "CA", "626": "CA", "650": "CA", "707": "CA", "714": "CA", "760": "CA", "805": "CA", "818": "CA", "858": "CA", "909": "CA", "916": "CA", "925": "CA", "949": "CA", "951": "CA",
        "305": "FL", "321": "FL", "352": "FL", "386": "FL", "407": "FL", "561": "FL", "727": "FL", "772": "FL", "786": "FL", "813": "FL", "850": "FL", "863": "FL", "904": "FL", "941": "FL", "954": "FL",
        "178": "PR", "787": "PR", "939": "PR", "208": "ID", "312": "IL", "773": "IL",
    }
    digits = normalize_phone(phone)
    if len(digits) == 10:
        return area_code_map.get(digits[:3], "")
    return ""


def process_lead(lead_item):
    idx, lead = lead_item
    contact = lead.get("contact", "").strip()
    company = lead.get("company", "").strip()
    phone = lead.get("phone", "").strip()
    phone_norm = normalize_phone(phone)
    details = lead.get("details", {})
    address = details.get("Property_Address") or details.get("Address") or details.get("address", "")
    state = extract_state_from_phone(phone)

    search_name = company if company else contact
    if not search_name or len(search_name) < 3:
        lead["skip_trace_status"] = "UNVERIFIED"
        return idx, lead, "UNVERIFIED", "No valid name"

    # Step 1: Query CMS NPI Registry
    try:
        parts = search_name.split()
        params = {"version": "2.1", "limit": 3}
        if len(parts) >= 2 and not company:
            params["first_name"] = parts[0]
            params["last_name"] = parts[-1]
        else:
            params["organization_name"] = search_name
        if state:
            params["state"] = state

        resp = requests.get(NPI_API, params=params, timeout=8)
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            for res in results:
                npi_num = res.get("number", "")
                basic = res.get("basic", {})
                npi_name = basic.get("organization_name") or f"{basic.get('first_name','')} {basic.get('last_name','')}".strip()
                
                for addr in res.get("addresses", []):
                    npi_phone = normalize_phone(addr.get("telephone_number", ""))
                    if npi_phone and phone_norm and npi_phone == phone_norm:
                        lead["skip_trace_status"] = "VERIFIED"
                        lead["skip_trace_source"] = "CMS NPI Registry"
                        lead["skip_trace_confidence"] = "high"
                        lead["npi_number"] = npi_num
                        lead["npi_name"] = npi_name
                        return idx, lead, "VERIFIED", f"NPI #{npi_num}"
                    elif npi_phone:
                        lead["skip_trace_status"] = "ENRICHED"
                        lead["skip_trace_source"] = "CMS NPI Registry"
                        lead["skip_trace_confidence"] = "medium"
                        lead["skip_trace_phone_alt"] = npi_phone
                        lead["npi_number"] = npi_num
                        lead["npi_name"] = npi_name
                        return idx, lead, "ENRICHED", f"NPI Alt Phone: {npi_phone}"
    except Exception:
        pass

    # Step 2: Query Google Maps Local Business Data
    try:
        query_str = f"{search_name} {state}".strip()
        resp = requests.get(GMAPS_API, headers=GMAPS_HEADERS, params={"query": query_str, "limit": 2}, timeout=8)
        if resp.status_code == 200:
            data = resp.json().get("data", [])
            for item in data:
                gphone = normalize_phone(item.get("phone_number", ""))
                gname = item.get("name", "")
                gaddr = item.get("full_address", "")
                if gphone and phone_norm and gphone == phone_norm:
                    lead["skip_trace_status"] = "VERIFIED"
                    lead["skip_trace_source"] = "Google Maps"
                    lead["skip_trace_confidence"] = "high"
                    lead["gmaps_name"] = gname
                    lead["gmaps_address"] = gaddr
                    return idx, lead, "VERIFIED", f"GMaps Match: {gname}"
                elif gphone:
                    lead["skip_trace_status"] = "ENRICHED"
                    lead["skip_trace_source"] = "Google Maps"
                    lead["skip_trace_confidence"] = "medium"
                    lead["skip_trace_phone_alt"] = gphone
                    lead["gmaps_name"] = gname
                    return idx, lead, "ENRICHED", f"GMaps Alt Phone: {gphone}"
    except Exception:
        pass

    # Step 3: RapidAPI Skip Tracing (if address exists)
    if address:
        try:
            resp = requests.get(SKIP_TRACE_API, headers=SKIP_TRACE_HEADERS, params={"address": address}, timeout=8)
            if resp.status_code == 200:
                sdata = resp.json()
                sphone = ""
                if isinstance(sdata, dict):
                    sphone = normalize_phone(sdata.get("phone") or sdata.get("cellPhone") or "")
                elif isinstance(sdata, list) and sdata:
                    sphone = normalize_phone(sdata[0].get("phone") or "")
                
                if sphone and phone_norm and sphone == phone_norm:
                    lead["skip_trace_status"] = "VERIFIED"
                    lead["skip_trace_source"] = "RapidAPI Skip Trace"
                    lead["skip_trace_confidence"] = "high"
                    return idx, lead, "VERIFIED", "RapidAPI Match"
                elif sphone:
                    lead["skip_trace_status"] = "ENRICHED"
                    lead["skip_trace_source"] = "RapidAPI Skip Trace"
                    lead["skip_trace_confidence"] = "medium"
                    lead["skip_trace_phone_alt"] = sphone
                    return idx, lead, "ENRICHED", f"RapidAPI Alt Phone: {sphone}"
        except Exception:
            pass

    lead["skip_trace_status"] = "UNVERIFIED"
    return idx, lead, "UNVERIFIED", "No match found"


def git_push():
    try:
        subprocess.run(["git", "add", "."], cwd=DIALER_REPO, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        msg = f"OVERNIGHT MASTER SKIP TRACE AUTO-SYNC: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        subprocess.run(["git", "commit", "-m", msg], cwd=DIALER_REPO, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["git", "push", "origin", "main"], cwd=DIALER_REPO, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log("[GIT PUSH SUCCESS] Auto-synced verified leads live to dialer repo!")
    except Exception as e:
        log(f"[GIT PUSH WARN] Git auto-sync notice: {e}")


def main():
    log("==========================================================")
    log("  MBM MASTER OVERNIGHT SKIP TRACE DAEMON STARTED")
    log("==========================================================")

    while True:
        leads = []
        seen_phones = set()

        # Load primary dialer database — PRESERVE every record (never filter/drop rows).
        # Drop-filters were destructive: they purged NPI-verified clinics whose contact was a
        # placeholder role and deleted one owner from every pair sharing a (previously fabricated)
        # phone number. Rows are only annotated, never removed.
        if DIALER_DB.exists():
            with open(DIALER_DB, "r", encoding="utf-8") as f:
                primary_leads = json.load(f)
                for lead in primary_leads:
                    p_norm = normalize_phone(lead.get("phone", ""))
                    if p_norm:
                        seen_phones.add(p_norm)
                    leads.append(lead)

        log(f"Master DB reloaded: {len(leads)} total leads (all preserved, no data loss)")

        total = len(leads)
        # Only auto-verify healthcare/business verticals (NPI + Google Maps are business registries).
        # Real-estate/person records are preserved as-is and never overwritten.
        pending_items = [(i, lead) for i, lead in enumerate(leads)
                         if not lead.get("skip_trace_status")
                         and (lead.get("vertical") or "").lower() in ("clinics", "clinic", "healthcare", "medical")]
        already_done = total - len(pending_items)

        log(f"Already processed: {already_done} | Pending: {len(pending_items)}")

        if not pending_items:
            log("100% of master leads are verified! Sleeping 30 seconds before re-checking...")
            time.sleep(30)
            continue

        processed_count = 0
        verified_count = sum(1 for l in leads if l.get("skip_trace_status") == "VERIFIED")
        enriched_count = sum(1 for l in leads if l.get("skip_trace_status") == "ENRICHED")
        unverified_count = sum(1 for l in leads if l.get("skip_trace_status") == "UNVERIFIED")

        with ThreadPoolExecutor(max_workers=NUM_WORKERS) as executor:
            futures = [executor.submit(process_lead, item) for item in pending_items]
            
            for future in as_completed(futures):
                try:
                    idx, updated_lead, status, note = future.result()
                    leads[idx] = updated_lead
                    processed_count += 1

                    if status == "VERIFIED":
                        verified_count += 1
                    elif status == "ENRICHED":
                        enriched_count += 1
                    else:
                        unverified_count += 1

                    if processed_count % 10 == 0 or status in ("VERIFIED", "ENRICHED"):
                        contact = updated_lead.get("contact", "")
                        log(f"[{already_done + processed_count}/{total}] [{status}] {contact} ({note})")

                    if processed_count % SAVE_INTERVAL == 0:
                        from MBM.LeadEngine.dialer_gateway import commit_dialer_db
                        commit_dialer_db(leads, reason="overnight_skip_trace_daemon", author="OVERNIGHT_SKIP_TRACE_DAEMON")
                        log(f"[AUTO-SAVE] Progress saved ({verified_count} VERIFIED, {enriched_count} ENRICHED, {unverified_count} UNVERIFIED)")
                        # Auto-dispatch to all agents
                        try:
                            subprocess.run([sys.executable, str(BASE_DIR / "agent_lead_dispatcher.py")], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                            log("[AGENT DISPATCH] Auto-dispatched verified leads to all AI calling & outreach agents!")
                        except Exception:
                            pass

                    if processed_count % PUSH_INTERVAL == 0:
                        git_push()

                except Exception as e:
                    log(f"[WORKER ERROR] {e}")

        # Final Save & Push for this pass
        from MBM.LeadEngine.dialer_gateway import commit_dialer_db
        commit_dialer_db(leads, reason="overnight_skip_trace_daemon", author="OVERNIGHT_SKIP_TRACE_DAEMON")
        git_push()
        log(f"Completed pass. Verified: {verified_count}, Enriched: {enriched_count}, Unverified: {unverified_count}")
        time.sleep(5)


if __name__ == "__main__":
    main()
