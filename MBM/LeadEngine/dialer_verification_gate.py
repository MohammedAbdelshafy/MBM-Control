#!/usr/bin/env python3
"""
Dialer Verification Gate — Owner-Verified Numbers Only
=======================================================
Single gatekeeper module imported by ALL dialers (close_queue, power, progressive).

A lead MUST pass ALL of these checks to be dialed:
  1. PHONE  → valid E.164, not 555/000, ≥10 digits
  2. NAME   → real person name (not placeholder/generic)
  3. VERIFIED → at least one verification source confirms:
     - skip_trace_status == "VERIFIED" or "ENRICHED" (with alt phone)
     - verification_status starts with "VERIFIED_"
     - source == "NPI" (government registry)
     - vertical == "Clinics" AND status == "QUEUED_FOR_AI_AGENT" AND NPI
       evidence present (npi number or NPI/CMS source). Status alone is NOT
       proof. GATE_ALLOW_UNPROVEN=1 restores lenient status-only acceptance
       for manual debugging; CI dialers must never set it.
     - NPI callsheet row carrying authorized_official_name + npi

Usage as module:
    from dialer_verification_gate import filter_for_dialer
    verified = filter_for_dialer(raw_leads)

Usage standalone:
    python dialer_verification_gate.py --audit            # audit all queues
    python dialer_verification_gate.py --file FILE.json   # audit one file
"""

import json
import os
import re
import sys
import csv
import argparse
from pathlib import Path
from datetime import datetime, timezone

sys.stdout.reconfigure(encoding="utf-8")

BASE = Path(__file__).resolve().parent

# ── Fake-data detection patterns ──────────────────────────────────────

FAKE_PHONE_RE = re.compile(
    r"(555[-\s]?\d{4})"           # 555 numbers
    r"|(^SR#)"                     # service request IDs
    r"|(^N/?A$)"                   # N/A
    r"|(^\s*$)"                    # blank
    r"|(\+1\s?\(\d{3}\)\s?555)"   # +1 (xxx) 555
    , re.IGNORECASE
)

BAD_EXCHANGES = {"555", "000"}

FAKE_NAME_MARKERS = [
    "action_required", "skip_trace", "unknown", "n/a",
    "distressed seller", "property owner", "hedge fund",
    "cash buyer", "acquisition group", "tbd", "pending",
    "placeholder", "test", "demo", "sample",
    "robert sterling", "elena rostova", "john doe", "jane doe",
]

# Synthetic / placeholder contact identities that must NEVER reach the dialer.
# These are the fallback labels historically produced by push scripts and the
# NPI callsheet when a real decision-maker name was unavailable.
PLACEHOLDER_NAME_MARKERS = [
    "practice principal", "managing doctor", "practice owner",
    "medical & dental practice", "medical and dental practice",
    "clinic director", "decision maker", "acquisitions partner",
    "licensed healthcare practitioner", "clinical director",
    "practice manager", "managing principal", "practice principal 0",
]


def _extract_phone(lead: dict) -> str:
    """Pull the best phone from any key name variant."""
    for key in ("verified_phone", "phone", "phone_number",
                "primary_phone", "contact_phone", "skip_trace_phone_alt"):
        val = lead.get(key, "")
        if val and str(val).strip():
            v = str(val).strip()
            # Skip placeholder tokens that are not real numbers
            # (e.g. "npi/registry" used as a verified_phone marker).
            if len(re.sub(r"\D", "", v)) < 7:
                continue
            return v
    return ""


def _extract_name(lead: dict) -> str:
    """Pull the best name from any key name variant."""
    for key in ("contact_name", "name", "contact", "owner_name",
                "authorized_official_name", "prospect_name",
                "skip_trace_owner_name", "provider_name",
                "organization_name", "company_name", "company"):
        val = lead.get(key, "")
        if val and str(val).strip():
            return str(val).strip()
    return ""


def _normalize_digits(phone: str) -> str:
    """Strip to digits only."""
    return re.sub(r"\D", "", phone)


# Foreign country calling codes that are NOT North American area codes.
# A "+1 531/Latin-America..." style number is a fabricated lead, never dialable.
# Also includes unassigned NANP ranges (211, 673, 683) and European country
# code ranges (37x) observed in fabricated fake rows.
FOREIGN_NANP_CODES = {
    "591", "592", "593", "594", "595", "596", "597", "598", "599",
    "502", "503", "504", "505", "506", "507", "961", "963", "964", "966",
    "971", "974", "992", "998",
    "211", "370", "371", "372", "373", "374", "375", "376", "377",
    "378", "379", "673", "683",
}


def is_valid_phone(phone: str) -> tuple[bool, str]:
    """Check phone validity. Returns (ok, reason)."""
    if not phone or not phone.strip():
        return False, "blank_phone"

    if FAKE_PHONE_RE.search(phone):
        return False, "fake_pattern_match"

    digits = _normalize_digits(phone)
    if len(digits) < 10:
        return False, f"too_short_{len(digits)}_digits"

    # Check exchange (digits 4-6 in a 10-digit US number)
    if len(digits) >= 10:
        # For 11-digit (1+10) take positions 4-6 of the 10-digit part
        d10 = digits[-10:]
        exchange = d10[3:6]
        if exchange in BAD_EXCHANGES:
            return False, f"bad_exchange_{exchange}"
        # Reject NANP-formatted numbers whose area code is actually a
        # foreign country code (fabricated 591/593/506... rows).
        if d10[:3] in FOREIGN_NANP_CODES:
            return False, f"foreign_area_code_{d10[:3]}"
        # Reject non-toll-free numbers ending in 000 (NPI registry
        # fax/placeholder numbers that are not callable).
        # TOLL_FREE_AREAS = {"800", "888", "877", "866", "855", "844", "833"}
        # if d10[-3:] == "000" and d10[:3] not in TOLL_FREE_AREAS:
        #     return False, "fake_suffix_000"

    return True, "ok"


def is_valid_name(name: str) -> tuple[bool, str]:
    """Check name validity. Returns (ok, reason)."""
    if not name or len(name.strip()) < 3:
        return False, "name_too_short"

    n_lower = name.strip().lower()
    for marker in FAKE_NAME_MARKERS:
        if marker in n_lower:
            return False, f"fake_name_marker:{marker}"

    # Must have at least 2 words (first + last) for personal names.
    # Exception: company names with "LLC", "Inc", "Corp" are allowed as single words.
    parts = name.strip().split()
    corp_markers = {"llc", "inc", "corp", "ltd", "co", "company", "group",
                    "solutions", "services", "medical", "clinic", "health",
                    "dental", "hospital", "center", "centre", "associates"}
    is_company = any(p.lower().rstrip(".,") in corp_markers for p in parts)
    if len(parts) < 2 and not is_company:
        return False, "single_word_name"

    return True, "ok"


def is_placeholder_identity(lead: dict) -> bool:
    """True when a lead carries a synthetic/placeholder contact identity.

    Guards the dialer against re-introducing placeholder names, synthetic
    contacts, and unverified NPI-only identities that rerank_top_100 removed.
    """
    name = _extract_name(lead).strip().lower()
    comp = ((lead.get("company_name") or lead.get("company") or "") + " "
            + ((lead.get("details") or {}).get("Owner_Name") or "")).strip().lower()
    combined = f"{name} {comp}"

    for marker in PLACEHOLDER_NAME_MARKERS:
        if marker in combined:
            return True

    # "Practice Principal <idx>" / "Acquisitions Partner <idx>" numbered fallbacks
    for pattern in (r"practice principal \d+", r"acquisitions partner \d+",
                    r"decision maker \d+", r"managing doctor \d+"):
        if re.search(pattern, combined):
            return True

    # Numbered generic fallbacks like "Lead 7", "Contact 12"
    if re.search(r"^(lead|contact|prospect|owner|principal)\s+\d+$", name):
        return True

    return False


def is_verified(lead: dict) -> tuple[bool, str]:
    """
    Check if the lead has at least one verification source.
    Returns (ok, source_description).
    """
    # 1. Skip trace verified
    st_status = (lead.get("skip_trace_status") or "").upper()
    if st_status == "VERIFIED":
        return True, "skip_trace_verified"

    # 2. Skip trace enriched WITH an alt phone
    if st_status == "ENRICHED" and lead.get("skip_trace_phone_alt"):
        return True, "skip_trace_enriched_alt_phone"

    # 3. Twilio Lookup verified
    v_status = (lead.get("verification_status") or "").upper()
    if v_status.startswith("VERIFIED_"):
        return True, f"twilio_{v_status.lower()}"

    # 4. NPI-sourced (government registry — always real).
    #    Registry proof may live at top level OR nested in `details`
    #    (leads_database clinics store it in details.source / details.npi_number).
    source = ((lead.get("source") or "") + " "
              + ((lead.get("details") or {}).get("source") or "")).upper()
    if "NPI" in source or "CMS" in source:
        return True, "npi_registry"

    # 5. NPI cold calling queue (vertical=Clinics from npi_verified_callsheet).
    #    A vertical + self-assigned workflow status is NOT proof of anything —
    #    any producer can stamp "QUEUED_FOR_AI_AGENT". STRICT by default: the
    #    row must also carry NPI evidence (an NPI number or NPI/CMS source).
    #    GATE_ALLOW_UNPROVEN=1 restores the old lenient behavior for manual
    #    debugging only — CI dialers must never set it.
    vertical = (lead.get("vertical") or lead.get("vertical_tag") or "").lower()
    status = (lead.get("status") or (lead.get("details") or {}).get("status") or "").upper()
    vertical = vertical or ((lead.get("details") or {}).get("vertical_tag") or "").lower()
    if vertical in ("clinics", "dentistry", "optometry", "chiropractic",
                     "physical therapy", "podiatry", "mental health",
                     "pharmacy", "nursing") and status == "QUEUED_FOR_AI_AGENT":
        if os.getenv("GATE_ALLOW_UNPROVEN", "").strip().lower() != "1":
            if not _has_npi_proof(lead):
                return False, "npi_cold_call_queue_no_proof"
        return True, "npi_cold_call_queue"

    # 6. NPI callsheet CSV lead (has authorized_official_name + npi).
    #    Accept nested `details` too.
    ao_name = lead.get("authorized_official_name") or (lead.get("details") or {}).get("authorized_official_name")
    npi = lead.get("npi") or lead.get("npi_number") or (lead.get("details") or {}).get("npi_number")
    if ao_name and npi:
        return True, "npi_callsheet"

    # 7. Explicit verified flag
    if lead.get("verified") == 1 or lead.get("verified") is True:
        return True, "explicit_verified_flag"

    return False, "unverified"


def _has_npi_proof(lead: dict) -> bool:
    """True when a row carries an actual NPI registry identifier."""
    if lead.get("npi") or lead.get("npi_number"):
        return True
    details = lead.get("details") or {}
    if details.get("npi_number") or details.get("npi"):
        return True
    source = ((lead.get("source") or "") + " " + str(details.get("source") or "")).upper()
    return "NPI" in source or "CMS" in source


def check_lead(lead: dict) -> dict:
    """
    Run all checks on a single lead. Returns a result dict:
    {
        "passed": bool,
        "phone": str,
        "name": str,
        "phone_ok": bool, "phone_reason": str,
        "name_ok": bool, "name_reason": str,
        "verified_ok": bool, "verified_source": str,
        "rejection_reasons": [str]
    }
    """
    phone = _extract_phone(lead)
    name = _extract_name(lead)

    phone_ok, phone_reason = is_valid_phone(phone)
    name_ok, name_reason = is_valid_name(name)
    verified_ok, verified_source = is_verified(lead)

    # ── Placeholder identity guard ──────────────────────────────────────
    # Synthetic/placeholder contacts must NEVER reach the dialer, even if they
    # clear the individual phone/name/verify checks. This gate is the final
    # authority and vetoes identities historically produced by push scripts and
    # the NPI callsheet when a real decision-maker name was unavailable.
    is_ph = is_placeholder_identity(lead)
    if is_ph:
        verified_ok = False
        verified_source = "placeholder_identity"

    reasons = []
    if not phone_ok:
        reasons.append(f"phone:{phone_reason}")
    if not name_ok:
        reasons.append(f"name:{name_reason}")
    if not verified_ok:
        reasons.append(f"verify:{verified_source}")

    return {
        "passed": phone_ok and name_ok and verified_ok,
        "phone": phone,
        "name": name,
        "phone_ok": phone_ok,
        "phone_reason": phone_reason,
        "name_ok": name_ok,
        "name_reason": name_reason,
        "verified_ok": verified_ok,
        "verified_source": verified_source,
        "rejection_reasons": reasons,
    }


def filter_for_dialer(leads: list[dict], quiet: bool = False) -> list[dict]:
    """
    Primary API — filters a list of leads, returning only verified-owner leads.

    Usage:
        from dialer_verification_gate import filter_for_dialer
        clean_leads = filter_for_dialer(raw_leads)
    """
    passed = []
    rejected = 0
    reasons_counter: dict[str, int] = {}

    for lead in leads:
        result = check_lead(lead)
        if result["passed"]:
            # Tag the lead with verification metadata
            lead["_gate_passed"] = True
            lead["_gate_source"] = result["verified_source"]
            passed.append(lead)
        else:
            rejected += 1
            for r in result["rejection_reasons"]:
                tag = r.split(":")[0]
                reasons_counter[tag] = reasons_counter.get(tag, 0) + 1

    if not quiet:
        total = len(leads)
        print(f"[GATE] {len(passed)}/{total} leads passed verification "
              f"({rejected} rejected)")
        if reasons_counter:
            parts = ", ".join(f"{k}={v}" for k, v in
                              sorted(reasons_counter.items(), key=lambda x: -x[1]))
            print(f"[GATE] Rejection breakdown: {parts}")

    return passed


# ── Standalone audit mode ─────────────────────────────────────────────

QUEUE_FILES = {
    "cold_calling_queue.json": BASE / "cold_calling_queue.json",
    "real_estate_calling_queue.json": BASE / "real_estate_calling_queue.json",
    "us_re_dialer_queue.json": BASE / "us_re_dialer_queue.json",
    "multi_touch_queue.json": BASE / "multi_touch_queue.json",
    "ulio_voice_queue.json": BASE / "ulio_voice_queue.json",
    "leads_database.json": Path(
        r"C:\Users\omare\OneDrive\Desktop\AI\mbm-dialer\app\public\leads_database.json"
    ),
}


def _load_any(path: Path) -> list[dict]:
    if not path.exists():
        return []
    if path.suffix.lower() == ".csv":
        with open(path, encoding="utf-8", errors="replace") as f:
            return list(csv.DictReader(f))
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        return data.get("queue", data.get("leads", data.get("data", [])))
    except Exception as exc:
        print(f"[WARN] Error loading {path.name}: {exc}")
        return []


def audit_file(path: Path, label: str = ""):
    label = label or path.name
    leads = _load_any(path)
    if not leads:
        print(f"\n[AUDIT] {label}: EMPTY or NOT FOUND")
        return

    results = [check_lead(l) for l in leads]
    passed = sum(1 for r in results if r["passed"])
    phone_fail = sum(1 for r in results if not r["phone_ok"])
    name_fail = sum(1 for r in results if not r["name_ok"])
    verify_fail = sum(1 for r in results if not r["verified_ok"])

    # By-source breakdown — exposes rows that "pass" only via the self-assigned
    # workflow status (npi_cold_call_queue) vs rows with real evidence.
    by_source: dict[str, int] = {}
    for r in results:
        if r["verified_ok"]:
            by_source[r["verified_source"]] = by_source.get(r["verified_source"], 0) + 1

    # Lenient projection — how many would pass if rule #5 accepted the
    # self-assigned workflow status without NPI evidence (GATE_ALLOW_UNPROVEN=1).
    # Strict is the default; this makes the rubber-stamp count visible.
    lenient_ok = 0
    os.environ["GATE_ALLOW_UNPROVEN"] = "1"
    try:
        for l in leads:
            ok, _ = is_verified(l)
            lenient_ok += 1 if ok else 0
    finally:
        os.environ.pop("GATE_ALLOW_UNPROVEN", None)

    print(f"\n{'='*60}")
    print(f"  [AUDIT] {label}")
    print(f"{'='*60}")
    print(f"  Total leads:        {len(leads)}")
    print(f"  PASSED (dial-ready): {passed}")
    print(f"  BLOCKED — bad phone: {phone_fail}")
    print(f"  BLOCKED — bad name:  {name_fail}")
    print(f"  BLOCKED — unverified:{verify_fail}")
    print(f"  Pass rate:           {passed/max(1,len(leads))*100:.1f}%")
    print(f"  -- lenient rule #5 (status-only, no NPI proof) would pass: {lenient_ok}")
    print(f"  Verified-by-source:  " + (", ".join(
        f"{k}={v}" for k, v in sorted(by_source.items(), key=lambda x: -x[1]))
        if by_source else "NONE"))
    print(f"{'='*60}")


def audit_all():
    print("=" * 60)
    print("  DIALER VERIFICATION GATE — FULL AUDIT")
    print(f"  {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    for name, path in QUEUE_FILES.items():
        audit_file(path, name)

    # Also check NPI callsheet
    npi = BASE.parent.parent / "MBM" / "Artifacts" / "npi_verified_callsheet.csv"
    if npi.exists():
        audit_file(npi, "npi_verified_callsheet.csv")


def main():
    ap = argparse.ArgumentParser(description="Dialer Verification Gate")
    ap.add_argument("--audit", action="store_true",
                    help="Audit all queue files")
    ap.add_argument("--file", type=str,
                    help="Audit a single file")
    args = ap.parse_args()

    if args.file:
        audit_file(Path(args.file))
    elif args.audit:
        audit_all()
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
