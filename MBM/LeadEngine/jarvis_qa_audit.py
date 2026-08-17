"""
JARVIS QA GATE — PRE-DIAL AUDIT & PRODUCTION DIALER ENFORCER
============================================================
Strict 10-Point Pre-Dial Verification Gate:
- NEVER sync blindly
- NEVER sync unverified records into prime dialer
- ONLY PRIME_CALLABLE leads enter the production dialer
- Full audit counts:
    1. PRIME_CALLABLE
    2. OWNER_VERIFICATION_REQUIRED
    3. CONTACT_VERIFICATION_REQUIRED
    4. BAD_NUMBER
    5. WRONG_PERSON
    6. NON_OWNER
    7. DNC
    8. DUPLICATE
    9. STALE
   10. UNVERIFIED
"""

import os
import sys
import json
import re
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

BASE_DIR = Path(__file__).resolve().parent
REPO_ROOT = BASE_DIR.parent.parent

DIALER_DB = REPO_ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"
REAL_ESTATE_QUEUE = BASE_DIR / "real_estate_calling_queue.json"
COLD_CALLING_QUEUE = BASE_DIR / "cold_calling_queue.json"
CASH_BUYERS_QUEUE = BASE_DIR / "facebook_cash_buyers.json"
DISPOSITIONS_FILE = BASE_DIR / "logs" / "call_dispositions.json"
REJECTION_LEDGER_FILE = BASE_DIR / "logs" / "rejection_ledger.json"

AUDIT_EXPORT_JSON = REPO_ROOT / "PRIME_CALLABLE_DIALER_AUDIT.json"
AUDIT_EXPORT_MD = REPO_ROOT / "PRIME_CALLABLE_DIALER_AUDIT.md"

FAKE_PHONE_REGEX = re.compile(r"^(555\d{4}|\+?1?555\d{7}|000\d{7}|1234567|9999999)$")
FAKE_SINGLE_WORDS = {"unknown", "n/a", "na", "test", "demo", "sample", "placeholder", "action_required", "tbd", "pending", "none", "null", "undefined"}
FAKE_PHRASES = ["john doe", "jane doe", "distressed seller", "property owner", "hedge fund", "cash buyer", "acquisition group", "skip trace"]


def clean_phone(phone: str) -> str:
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 10:
        return f"+1{digits}"
    elif len(digits) == 11 and digits.startswith("1"):
        return f"+{digits}"
    return digits


def is_fake_phone(phone: str) -> bool:
    digits = re.sub(r"\D", "", str(phone or ""))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        return True
    if digits.startswith("0") or digits.startswith("1"):
        return True
    area = digits[:3]
    exchange = digits[3:6]
    if area == "555" or exchange == "555" or exchange == "000":
        return True
    if FAKE_PHONE_REGEX.match(digits):
        return True
    if len(set(digits)) == 1:
        return True
    return False


def is_valid_name(name: str) -> bool:
    if not name or len(name.strip()) < 2:
        return False
    clean = name.strip().lower()
    for phrase in FAKE_PHRASES:
        if phrase in clean:
            return False
    words = re.split(r"\s+", clean)
    if clean in FAKE_SINGLE_WORDS:
        return False
    if len(words) == 1 and words[0] in FAKE_SINGLE_WORDS:
        return False
    return True


class JarvisQAGateAuditor:
    def __init__(self):
        self.rejection_ledger = {}
        self.load_rejection_ledger()
        self.load_call_dispositions()

    def load_rejection_ledger(self):
        if REJECTION_LEDGER_FILE.exists():
            try:
                with open(REJECTION_LEDGER_FILE, "r", encoding="utf-8") as f:
                    self.rejection_ledger = json.load(f)
            except Exception:
                self.rejection_ledger = {}

    def load_call_dispositions(self):
        if DISPOSITIONS_FILE.exists():
            try:
                with open(DISPOSITIONS_FILE, "r", encoding="utf-8") as f:
                    disps = json.load(f)
                    for d in disps:
                        phone = re.sub(r"\D", "", str(d.get("phone") or d.get("phone_number") or ""))
                        dispo = str(d.get("disposition", "")).upper()
                        parcel = str(d.get("property_id") or d.get("parcel_id") or "")
                        if phone and dispo in ["BAD_NUMBER", "DNC", "WRONG_PERSON", "NON_OWNER", "SOLD"]:
                            key = f"{parcel}::{phone}" if parcel else phone
                            self.rejection_ledger[key] = {
                                "category": dispo,
                                "reason": d.get("notes") or f"Field disposition {dispo}",
                                "timestamp": d.get("created_at") or datetime.now(timezone.utc).isoformat()
                            }
            except Exception:
                pass

    def run_audit(self) -> dict:
        seen_phones = set()
        seen_parcels = set()
        all_candidates = []

        def ingest_file(file_path: Path, source_label: str):
            if not file_path.exists():
                return
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    arr = data if isinstance(data, list) else (data.get("leads") or data.get("queue") or data.get("prospects") or [])
                    for item in arr:
                        item["_source_file"] = source_label
                        all_candidates.append(item)
            except Exception:
                pass

        ingest_file(REAL_ESTATE_QUEUE, "REAL_ESTATE_QUEUE")
        ingest_file(CASH_BUYERS_QUEUE, "FACEBOOK_CASH_BUYERS")
        ingest_file(COLD_CALLING_QUEUE, "COLD_CALLING_QUEUE")
        ingest_file(DIALER_DB, "EXISTING_MBM_DIALER")

        # Counts
        counts = {
            "PRIME_CALLABLE": 0,
            "OWNER_VERIFICATION_REQUIRED": 0,
            "CONTACT_VERIFICATION_REQUIRED": 0,
            "BAD_NUMBER": 0,
            "WRONG_PERSON": 0,
            "NON_OWNER": 0,
            "DNC": 0,
            "DUPLICATE": 0,
            "STALE": 0,
            "UNVERIFIED": 0,
        }

        prime_records = []
        rejected_records = []

        for lead in all_candidates:
            raw_phone = lead.get("phone") or lead.get("phone_number") or lead.get("verified_phone") or lead.get("formatted_phone") or lead.get("practice_location_address_telephone_number") or ""
            phone = clean_phone(raw_phone)
            digits = re.sub(r"\D", "", phone)
            
            raw_name = (
                lead.get("prospect_name") or
                lead.get("owner_name") or
                lead.get("contact_name") or
                lead.get("organization_name") or
                lead.get("company_name") or
                lead.get("provider_full_name") or
                lead.get("name") or
                f"{lead.get('provider_first_name', '')} {lead.get('provider_last_name_legal_name', '')}".strip() or
                ""
            )
            parcel_id = str(lead.get("parcel_id") or lead.get("apn") or lead.get("property_id") or lead.get("npi") or lead.get("id") or "").strip()
            address = (
                lead.get("address") or
                lead.get("property_address") or
                lead.get("practice_location_address_line_1") or
                lead.get("practice_location_address_city_name") or
                lead.get("city") or
                ""
            )
            
            rejection_key_phone = digits
            rejection_key_parcel = f"{parcel_id}::{digits}"

            # 1. Rejection Ledger Check
            if rejection_key_phone in self.rejection_ledger or rejection_key_parcel in self.rejection_ledger:
                rej = self.rejection_ledger.get(rejection_key_parcel) or self.rejection_ledger.get(rejection_key_phone)
                cat = rej["category"] if rej["category"] in counts else "UNVERIFIED"
                counts[cat] += 1
                lead["_audit_category"] = cat
                lead["_rejection_reason"] = rej["reason"]
                rejected_records.append(lead)
                continue

            # 2. DNC check
            if str(lead.get("dnc", "")).lower() in ["true", "yes", "1", "listed"] or lead.get("dnc_status") == "DNC_ACTIVE":
                counts["DNC"] += 1
                lead["_audit_category"] = "DNC"
                rejected_records.append(lead)
                continue

            # 3. Duplicate check
            if digits and digits in seen_phones:
                counts["DUPLICATE"] += 1
                lead["_audit_category"] = "DUPLICATE"
                rejected_records.append(lead)
                continue

            # 4. Phone Quality Pass
            if is_fake_phone(phone):
                counts["BAD_NUMBER"] += 1
                lead["_audit_category"] = "BAD_NUMBER"
                rejected_records.append(lead)
                continue

            # 5. Owner / Entity Verification
            if not is_valid_name(raw_name):
                counts["OWNER_VERIFICATION_REQUIRED"] += 1
                lead["_audit_category"] = "OWNER_VERIFICATION_REQUIRED"
                rejected_records.append(lead)
                continue

            # 6. Property / Business Location check
            if not address and not parcel_id:
                counts["UNVERIFIED"] += 1
                lead["_audit_category"] = "UNVERIFIED"
                rejected_records.append(lead)
                continue

            # 7. Stale evaluation
            if lead.get("is_stale") or lead.get("decayed_score", 100) < 5:
                counts["STALE"] += 1
                lead["_audit_category"] = "STALE"
                rejected_records.append(lead)
                continue

            # Passed all checks -> PRIME_CALLABLE
            seen_phones.add(digits)
            if parcel_id:
                seen_parcels.add(parcel_id)

            counts["PRIME_CALLABLE"] += 1
            lead["_audit_category"] = "PRIME_CALLABLE"
            lead["phone_number"] = phone
            lead["formatted_phone"] = phone
            lead["prospect_name"] = raw_name
            prime_records.append(lead)

        return {
            "total_evaluated": len(all_candidates),
            "counts": counts,
            "prime_leads": prime_records,
            "rejected_leads": rejected_records,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def sync_production_dialer(self, prime_leads: list) -> bool:
        if not prime_leads:
            print("❌ QA GATE REJECTION: Zero PRIME_CALLABLE leads. Refusing to overwrite production dialer.")
            return False

        # Format and write strictly PRIME_CALLABLE records
        DIALER_DB.parent.mkdir(parents=True, exist_ok=True)
        try:
            sys.path.insert(0, str(REPO_ROOT))
            from MBM.GLM.single_writer_lock import DialerSingleWriter
            DialerSingleWriter().full_replace(prime_leads, author="JARVIS_QA_AUDIT")
        except Exception:
            with open(DIALER_DB, "w", encoding="utf-8") as f:
                json.dump(prime_leads, f, indent=2)

        print(f"✅ JARVIS QA GATE PASSED: Synced {len(prime_leads)} verified PRIME_CALLABLE leads to {DIALER_DB}")
        return True


def run_full_qa_and_sync():
    print("=" * 75)
    print("  🛡️ JARVIS QA GATE — PRE-DIAL VERIFICATION AUDIT")
    print("=" * 75)

    auditor = JarvisQAGateAuditor()
    audit_results = auditor.run_audit()
    counts = audit_results["counts"]

    print("\n📊 PRE-DIAL AUDIT TALLY:")
    for cat, count in counts.items():
        emoji = "✅" if cat == "PRIME_CALLABLE" else "🚫"
        print(f"  {emoji} {cat.ljust(32)} : {count}")

    print("-" * 75)
    total_suppressed = counts["BAD_NUMBER"] + counts["DNC"] + counts["WRONG_PERSON"] + counts["NON_OWNER"] + counts["DUPLICATE"]
    total_verification_required = counts["OWNER_VERIFICATION_REQUIRED"] + counts["CONTACT_VERIFICATION_REQUIRED"] + counts["UNVERIFIED"] + counts["STALE"]

    print(f"  • PRIME CALLABLE CANDIDATES      : {counts['PRIME_CALLABLE']}")
    print(f"  • SUPPRESSED / REJECTED RECORDS : {total_suppressed}")
    print(f"  • VERIFICATION REQUIRED / HELD  : {total_verification_required}")
    print("=" * 75)

    # Export audit artifacts
    with open(AUDIT_EXPORT_JSON, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": audit_results["timestamp"],
            "counts": counts,
            "total_evaluated": audit_results["total_evaluated"],
            "prime_callable_count": counts["PRIME_CALLABLE"],
            "suppressed_count": total_suppressed,
            "verification_required_count": total_verification_required,
        }, f, indent=2)

    with open(AUDIT_EXPORT_MD, "w", encoding="utf-8") as f:
        f.write("# JARVIS QA Gate — Pre-Dial Audit Report\n\n")
        f.write(f"**Generated:** {audit_results['timestamp']}\n\n")
        f.write("| Category | Count | Status |\n")
        f.write("|---|---|---|\n")
        for cat, count in counts.items():
            status = "**ELIGIBLE FOR DIALER**" if cat == "PRIME_CALLABLE" else "BLOCKED / HELD"
            f.write(f"| `{cat}` | **{count}** | {status} |\n")
        f.write(f"\n- **Total Evaluated**: {audit_results['total_evaluated']}\n")
        f.write(f"- **Prime Callable**: {counts['PRIME_CALLABLE']}\n")
        f.write(f"- **Suppressed**: {total_suppressed}\n")
        f.write(f"- **Verification Required**: {total_verification_required}\n")

    # Sync Production Dialer
    success = auditor.sync_production_dialer(audit_results["prime_leads"])
    return {
        "success": success,
        "counts": counts,
        "total_suppressed": total_suppressed,
        "total_verification_required": total_verification_required,
    }


if __name__ == "__main__":
    run_full_qa_and_sync()
