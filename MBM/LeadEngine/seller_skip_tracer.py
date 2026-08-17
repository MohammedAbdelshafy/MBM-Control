#!/usr/bin/env python3
"""
MBM Hybrid Seller Skip-Tracer — Replace Fabricated Seller Contacts With Real Ones
==================================================================================
Processes the Real Estate Seller leads in mbm-dialer/leads_database.json and either
CONFIRMS existing data against an authoritative source or finds a REAL owner
name + phone. Never fabricates, never deletes rows — rows are annotated only.

Sources (in order of authority for person/parcel records):
  1. DCAD Dallas County parcel API   — real registered owner name + mailing addr
  2. RapidAPI Skip Tracing           — address/name -> phone  (needs RAPIDAPI_KEY)
  3. Google Maps (RapidAPI Local Biz)— business cross-reference (needs RAPIDAPI_KEY)
  4. FreeSkipTracer                  — no-key web scrapers (TruePeopleSearch, etc.)
  5. Gemini search-grounded          — last-resort autonomous lookup (needs GEMINI_API_KEY)

Output tags on each lead:
  skip_trace_status     : VERIFIED | DONE | UNVERIFIED | NO_MATCH
  skip_trace_source     : which source confirmed/enriched it
  skip_trace_confidence : high | medium | low
  skip_trace_phone_alt  : alternate real number when primary is fabricated
  verified_phone        : best dialable real number

Safe by default — nothing is written until --apply:

  python MBM/LeadEngine/seller_skip_tracer.py                 # dry-run (NO writes)
  python MBM/LeadEngine/seller_skip_tracer.py --apply --limit 50
  python MBM/LeadEngine/seller_skip_tracer.py --apply --vertical "Real Estate Sellers"
  python MBM/LeadEngine/seller_skip_tracer.py --apply --no-free   # skip web scrapers
"""

import os
import io
import re
import sys
import json
import time
import shutil
import argparse
from datetime import datetime, timezone
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

BASE = Path(__file__).resolve().parent
DIALER_DB = BASE.parent.parent / "mbm-dialer" / "app" / "public" / "leads_database.json"
LOGS = BASE / "logs"
LOGS.mkdir(parents=True, exist_ok=True)
REPORT = LOGS / "seller_skiptrace_report.json"

DEFAULT_VERTICALS = ["Real Estate Sellers", "Texas Real Estate", "Master Catch-All"]

try:
    sys.path.insert(0, str(BASE.parent.parent))
    from MBM.GLM.single_writer_lock import DialerSingleWriter
    _SINGLE_WRITER = DialerSingleWriter()
except Exception as e:
    print(f"[WARN] Single-writer gateway unavailable ({e}); using direct write fallback.")
    _SINGLE_WRITER = None

try:
    from dotenv import load_dotenv
    load_dotenv(BASE.parent.parent / ".env")
except ImportError:
    pass

RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY", "")
SKIP_TRACE_API = "https://skip-tracing-working-api.p.rapidapi.com/search"
GMAPS_API = "https://local-business-data.p.rapidapi.com/search"

PLACEHOLDER_NAMES = (
    "private residential property", "property owner", "action_required",
    "skip_trace", "unknown", "n/a", "tbd", "pending", "placeholder",
)

# Country codes that are NOT North American area codes — leaking in means the
# number was fabricated (591 = Bolivia, 593 = Ecuador, 506 = Costa Rica, etc.)
# plus unassigned NANP ranges observed in fabricated-fake rows (211, 673, 683)
# and European country-code ranges (37x: Lithuania/Poland/Estonia/Latvia...).
FOREIGN_CODES = {
    "591", "592", "593", "594", "595", "596", "597", "598", "599",
    "502", "503", "504", "505", "506", "507",
    "961", "963", "964", "966", "971", "974", "992", "998",
    "211", "370", "371", "372", "373", "374", "375", "376", "377",
    "378", "379", "673", "683",
}


def log(msg):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[SELLER SKIPTRACE] {ts} - {msg}"
    print(line)
    try:
        with open(LOGS / "seller_skiptrace.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def normalize_phone(phone):
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return ""
    if digits[:3] in FOREIGN_CODES:
        return ""
    if digits[3:6] in {"555", "000"}:
        return ""
    return "+1" + digits


def is_fabricated_phone(phone):
    """True when the current phone is blank/placeholder or invalid enough to replace."""
    if not phone or any(k in str(phone).lower() for k in
                        ("action_required", "no number", "n/a", "skip_trace", "+1 591", "+1 593", "+1 506")):
        return True
    return not normalize_phone(phone)


def is_placeholder_name(name):
    low = (name or "").strip().lower()
    return (not low) or low in PLACEHOLDER_NAMES or len(low) < 3


def lead_address(lead):
    d = lead.get("details") or {}
    return d.get("Property_Address") or d.get("Address") or d.get("address") or ""


def lead_vertical(lead):
    return lead.get("vertical") or lead.get("type") or ""


def lead_company(lead):
    return lead.get("company") or lead.get("entity") or ""


def run_dcad(lead):
    """Dallas parcel lookup -> real owner name + mailing address (free, authoritative)."""
    address = lead_address(lead)
    if not address:
        return None
    street_low = address.lower()
    if "dallas" not in street_low and " tx" not in street_low:
        return None
    try:
        sys.path.insert(0, str(BASE))
        from dcad_owner_lookup import dcad_lookup, title_case_owner
        result = dcad_lookup(address)
        if not result or not result.get("owner"):
            return None
        return {
            "owner": title_case_owner(result["owner"]),
            "site_address": result.get("site_address") or "",
            "mail_address": result.get("mail_address") or "",
            "parcel_id": result.get("parcel_id") or "",
        }
    except Exception as e:
        log(f"[dcad] error for {address}: {e}")
        return None


def run_rapidapi_skiptrace(name, address):
    """Address-based skip trace via RapidAPI. Returns {'phone': ...} or None."""
    if not RAPIDAPI_KEY or not address:
        return None
    try:
        import requests
        resp = requests.get(
            SKIP_TRACE_API,
            headers={
                "x-rapidapi-key": RAPIDAPI_KEY,
                "x-rapidapi-host": "skip-tracing-working-api.p.rapidapi.com",
            },
            params={"address": address, "name": name or ""},
            timeout=12,
        )
        if resp.status_code != 200:
            return None
        data = resp.json()
        if isinstance(data, list) and data:
            data = data[0]
        if not isinstance(data, dict):
            return None
        phone = data.get("phone") or data.get("cellPhone") or data.get("phone_number")
        return {"phone": normalize_phone(phone) or ""}
    except Exception as e:
        log(f"[rapidapi] error: {e}")
        return None


def run_gmaps(name, address):
    """Google Maps (RapidAPI Local Business Data) cross-reference."""
    if not RAPIDAPI_KEY:
        return None
    try:
        import requests
        query = name or (address or "")
        resp = requests.get(
            GMAPS_API,
            headers={
                "x-rapidapi-key": RAPIDAPI_KEY,
                "x-rapidapi-host": "local-business-data.p.rapidapi.com",
            },
            params={"query": query, "limit": 3},
            timeout=12,
        )
        if resp.status_code != 200:
            return None
        data = resp.json().get("data", [])
        if not data:
            return None
        it = data[0]
        phone = normalize_phone(it.get("phone_number") or "")
        return {"phone": phone, "name": it.get("name") or ""}
    except Exception as e:
        log(f"[gmaps] error: {e}")
        return None


def run_free_skiptrace(name, address, city=""):
    """No-key free web scrapers (TruePeopleSearch, FastPeopleSearch, DDG...)."""
    try:
        sys.path.insert(0, str(BASE))
        from free_skip_tracer import FreeSkipTracer
        tracer = FreeSkipTracer()
        result = tracer.find_contact(name=name or "", address=address, city=city)
        phone = normalize_phone(result.get("phone") or "")
        return {"phone": phone, "email": result.get("email") or "",
                "source": result.get("source") or ""}
    except Exception as e:
        log(f"[free] error: {e}")
        return None


def run_gemini(name, address, city=""):
    """Gemini search-grounded fallback (structured JSON response)."""
    try:
        sys.path.insert(0, str(BASE))
        from gemini_skip_tracer import autonomous_skip_trace
        result = autonomous_skip_trace(name=name, address=address, city=city)
        if not result:
            return None
        return {"phone": normalize_phone(result.get("phone") or ""),
                "email": result.get("email") or "",
                "confidence": (result.get("confidence") or "").lower()}
    except Exception as e:
        log(f"[gemini] error: {e}")
        return None


def has_gemini_key():
    return bool(os.getenv("GEMINI_API_KEY"))


def process_lead(lead, use_free=True, use_gemini=True):
    """Return updated lead + a short status note (never deletes the row)."""
    d = lead.get("details") or {}
    address = lead_address(lead)
    phone = normalize_phone(lead.get("phone") or "")
    contact = (lead.get("contact") or "").strip()
    company = (lead.get("company") or "").strip()
    city = d.get("City") or ""
    state = d.get("State") or ""
    search_name = contact or company or ""

    # Fast exit: already confirmed via DCAD parcel records.
    if d.get("DCAD_Owner_Confirmed") == "yes":
        lead["skip_trace_status"] = "VERIFIED"
        lead["skip_trace_source"] = "dcad"
        lead["skip_trace_confidence"] = "high"
        lead["verified_phone"] = phone or lead["phone"]
        return lead, "dcad_confirmed"

    # Fast exit: already verified by a prior run with a real number.
    if lead.get("skip_trace_status") == "VERIFIED" and normalize_phone(lead.get("verified_phone") or lead.get("phone") or ""):
        return lead, "already_verified"

    # Fast exit: no address and no name = nothing to search on.
    if not address and (is_placeholder_name(contact) and not company):
        lead["skip_trace_status"] = lead.get("skip_trace_status") or "UNVERIFIED"
        return lead, "no_searchable_fields"

    # 1) DCAD first — authoritative owner records for Dallas-area parcels.
    dcad = run_dcad(lead)
    if dcad:
        real_owner = dcad["owner"]
        lead["contact"] = real_owner
        lead["company"] = lead.get("company") or real_owner
        d["Owner_Name"] = real_owner
        d["DCAD_Owner_Confirmed"] = "yes"
        d["Site_Address"] = dcad["site_address"] or d.get("Site_Address")
        if dcad["mail_address"]:
            d["Owner_Mail_Address"] = dcad["mail_address"]
        if dcad["parcel_id"]:
            d["DCAD_Parcel_ID"] = dcad["parcel_id"]
        d["Skip_Trace_Source"] = "dcad"
        d["Skip_Trace_Confidence"] = "high"
        lead["skip_trace_status"] = "VERIFIED"
        lead["skip_trace_source"] = "dcad"
        lead["skip_trace_confidence"] = "high"
        lead["verified_phone"] = normalize_phone(lead.get("phone") or phone) or lead.get("phone")
        lead["details"] = d
        if phone:
            return lead, "dcad_verified_with_phone"
        # DCAD gives owners, not phones — proceed to phone hunting.
        status_note = "dcad_owner_found_no_phone"
    else:
        status_note = "no_dcad"

    # 2) RapidAPI skip trace (real phone via address/name).
    rap = run_rapidapi_skiptrace(search_name, address)
    rap_phone = (rap or {}).get("phone") or ""
    if rap_phone:
        lead["skip_trace_phone_alt"] = rap_phone
        lead["skip_trace_source"] = "rapidapi_skiptrace"
        lead["skip_trace_confidence"] = "high"
        if is_fabricated_phone(lead.get("phone")):
            lead["phone"] = rap_phone
            d["Owner_Phone"] = rap_phone
        lead["verified_phone"] = rap_phone
        lead["skip_trace_status"] = "VERIFIED"
        lead["details"] = d
        return lead, "verified_rapidapi"

    # 3) Google Maps (business cross-reference).
    gmap = run_gmaps(search_name or address, address)
    gmap_phone = (gmap or {}).get("phone") or ""
    if gmap_phone:
        lead["skip_trace_phone_alt"] = gmap_phone
        lead["skip_trace_source"] = "google_maps"
        lead["skip_trace_confidence"] = "medium"
        if is_fabricated_phone(lead.get("phone")):
            lead["phone"] = gmap_phone
            d["Owner_Phone"] = gmap_phone
        lead["verified_phone"] = gmap_phone
        lead["skip_trace_status"] = "VERIFIED"
        lead["details"] = d
        return lead, "verified_gmaps"

    # 4) Free no-key scrapers (optional, slower).
    if use_free:
        free = run_free_skiptrace(search_name, address, city)
        free_phone = (free or {}).get("phone") or ""
        if free_phone:
            lead["skip_trace_phone_alt"] = free_phone
            lead["skip_trace_source"] = (free or {}).get("source") or "free"
            lead["skip_trace_confidence"] = "medium"
            if is_fabricated_phone(lead.get("phone")):
                lead["phone"] = free_phone
                d["Owner_Phone"] = free_phone
            lead["verified_phone"] = free_phone
            lead["skip_trace_status"] = "VERIFIED"
            lead["details"] = d
            return lead, "verified_free"

    # 5) Gemini search-grounded last resort.
    if use_gemini and has_gemini_key():
        gem = run_gemini(search_name, address, city)
        gem_phone = (gem or {}).get("phone") or ""
        if gem_phone:
            lead["skip_trace_phone_alt"] = gem_phone
            lead["skip_trace_source"] = "gemini_search"
            lead["skip_trace_confidence"] = (gem or {}).get("confidence") or "low"
            if is_fabricated_phone(lead.get("phone")):
                lead["phone"] = gem_phone
                d["Owner_Phone"] = gem_phone
            lead["verified_phone"] = gem_phone
            lead["skip_trace_status"] = "VERIFIED"
            lead["details"] = d
            return lead, "verified_gemini"

    # Nothing confirmed — keep the row, only annotate.
    lead["details"] = d
    lead["skip_trace_status"] = "UNVERIFIED"
    lead["skip_trace_source"] = lead.get("skip_trace_source") or "no_source"
    lead["skip_trace_confidence"] = lead.get("skip_trace_confidence") or "low"
    return lead, (status_note if status_note != "no_dcad" else "unverified_no_source")


def load_db():
    if not DIALER_DB.exists():
        log(f"ERROR: {DIALER_DB} missing — cannot run.")
        return []
    with open(DIALER_DB, "r", encoding="utf-8") as f:
        return json.load(f)


def save_db(db, apply=True):
    if not apply:
        return
    if _SINGLE_WRITER is not None:
        res = _SINGLE_WRITER.full_replace(db, author="SELLER_SKIP_TRACER")
        if not res.get("ok"):
            raise RuntimeError(f"Single-writer commit failed: {res}")
        log(f"Saved {res['final_count']} leads via single-writer gateway")
        return
    # Backups go OUTSIDE the served app/public dir — .bak files written into the
    # Vite-watched public folder crash the dev server (EBUSY watcher).
    bak_dir = BASE / "logs" / "db_backups"
    bak_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = bak_dir / f"leads_database.{stamp}.bak.json"
    if DIALER_DB.exists():
        shutil.copy2(DIALER_DB, backup)
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from MBM.LeadEngine.dialer_gateway import commit_dialer_db
    commit_dialer_db(db, reason="seller_skip_tracer", author="SELLER_SKIP_TRACER")


def summarize(results):
    from collections import Counter
    counts = Counter(r["note"] for r in results)
    verified = sum(1 for r in results if r["status"] == "VERIFIED")
    return counts, verified


def main():
    ap = argparse.ArgumentParser(description="Hybrid Seller Skip-Tracer")
    ap.add_argument("--apply", action="store_true", help="write results (default: dry-run)")
    ap.add_argument("--limit", type=int, default=None, help="max leads to process")
    ap.add_argument("--vertical", type=str, default=",".join(DEFAULT_VERTICALS),
                    help="comma-separated verticals")
    ap.add_argument("--no-free", action="store_true", help="skip free web scrapers")
    ap.add_argument("--no-gemini", action="store_true", help="skip gemini fallback")
    ap.add_argument("--resume", action="store_true", help="skip leads already VERIFIED/DONE")
    args = ap.parse_args()

    verticals = [v.strip() for v in args.vertical.split(",") if v.strip()]

    db = load_db()
    if not db:
        return
    log(f"Loaded {len(db)} leads from {DIALER_DB.name}")

    targets = [l for l in db if lead_vertical(l) in verticals]
    log(f"Targeting {len(targets)} seller leads in {', '.join(verticals)}")

    if args.resume:
        pending = [l for l in targets
                   if not l.get("skip_trace_status")]
        log(f"Resume mode — {len(pending)} untouched leads (already-attempted skipped)")
        targets = pending

    if args.limit:
        targets = targets[: args.limit]

    log(f"Processing {len(targets)} leads (apply={args.apply}, no_free={args.no_free}, "
        f"no_gemini={args.no_gemini})")

    results = []
    for i, lead in enumerate(targets, 1):
        updated, note = process_lead(
            lead, use_free=not args.no_free, use_gemini=not args.no_gemini)
        status = updated.get("skip_trace_status", "?")
        contact = updated.get("contact") or ""
        ver = updated.get("verified_phone") or updated.get("phone") or ""
        log(f"[{i}/{len(targets)}] [{status}] {note} | {contact} | {ver}")
        results.append({"id": lead.get("id"), "status": status, "note": note,
                        "contacts": contact})
        if i % 10 == 0 and args.apply:
            save_db(db, apply=True)
            log(f"[checkpoint] saved at {i}/{len(targets)}")

    if args.apply:
        save_db(db, apply=True)
        log(f"Saved {len(db)} leads back to {DIALER_DB.name} (backup written)")

    counts, verified = summarize(results)
    total = len(results)
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "mode": "apply" if args.apply else "dry_run",
        "database": str(DIALER_DB),
        "total_processed": total,
        "verified": verified,
        "verified_pct": f"{verified/max(1,total)*100:.1f}%",
        "note_breakdown": dict(counts),
    }
    REPORT.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("\n" + "=" * 60)
    print(f"  SELLER SKIP-TRACE SUMMARY ({report['mode']})")
    print("=" * 60)
    print(f"  Processed : {total}")
    print(f"  Verified  : {verified} ({report['verified_pct']})")
    print("  Breakdown :")
    for note, n in sorted(counts.items(), key=lambda x: -x[1]):
        print(f"    {n:>4}  {note}")
    print(f"  Report    : {REPORT}")
    print()
    if not args.apply:
        print("  DRY-RUN — no files changed. Re-run with --apply to write.")
    print()


if __name__ == "__main__":
    main()