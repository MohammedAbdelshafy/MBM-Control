#!/usr/bin/env python3
"""
PERMANENT HISTORICAL EXCLUSION LEDGER
=============================================================================
Single source of truth tracking all leads, phones, emails, identities, and
dispositions ever seen in the MBM system.

Guarantees:
- Global deduplication across all time (not just today)
- Prevents recycling of stale leads into active dialer inventory
- Tracks first_seen_date, last_seen_date, and historical status
- Fast in-memory lookup indices for sub-millisecond deduplication
=============================================================================
"""

import re
import sys
import json
from pathlib import Path
from typing import Dict, Any, List, Set, Tuple, Optional
from datetime import datetime, timezone

ROOT_DIR = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = ROOT_DIR / "MBM" / "Artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
LEDGER_PATH = ARTIFACTS_DIR / "lead_history_ledger.json"


def normalize_phone_digits(phone: str) -> str:
    """Normalize US phone to 10 raw digits."""
    if not phone:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    if len(digits) == 10:
        return digits
    return digits


def normalize_email_address(email: str) -> str:
    """Normalize email address to lowercase stripped."""
    if not email or not isinstance(email, str):
        return ""
    return email.strip().lower()


def normalize_name_key(name: str, company: str = "") -> str:
    """Create normalized person+company composite key."""
    clean_name = re.sub(r"[^a-zA-Z0-9]", "", str(name or "")).lower()
    clean_co = re.sub(r"[^a-zA-Z0-9]", "", str(company or "")).lower()
    return f"{clean_name}@{clean_co}" if clean_co else clean_name


class LeadHistoryLedger:
    """
    Durable historical exclusion ledger preventing recycling of seen leads.
    """

    def __init__(self, ledger_file: Optional[Path] = None):
        self.ledger_file = ledger_file or LEDGER_PATH
        self.records: Dict[str, Dict[str, Any]] = {}
        
        # Fast Index Sets
        self.seen_phones: Set[str] = set()
        self.seen_emails: Set[str] = set()
        self.seen_names: Set[str] = set()
        self.seen_properties: Set[str] = set()
        self.seen_lead_ids: Set[str] = set()

        self._load()
        if len(self.records) == 0:
            self.bootstrap_from_existing_data()

    def _load(self) -> None:
        """Load ledger from JSON file and rebuild index sets."""
        if self.ledger_file.exists():
            try:
                data = json.loads(self.ledger_file.read_text(encoding="utf-8"))
                for rec in data:
                    key = rec.get("identity_key") or rec.get("phone") or rec.get("lead_id")
                    if key:
                        self.records[key] = rec
                        self._index_record(rec)
            except Exception as e:
                print(f"[WARN] Error loading history ledger from {self.ledger_file}: {e}")

    def _index_record(self, rec: Dict[str, Any]) -> None:
        """Index a single record into lookup sets."""
        p = rec.get("norm_phone") or normalize_phone_digits(rec.get("phone", ""))
        if p and len(p) == 10:
            self.seen_phones.add(p)

        e = rec.get("norm_email") or normalize_email_address(rec.get("email", ""))
        if e and "@" in e and not e.endswith("example.com"):
            self.seen_emails.add(e)

        nk = rec.get("name_key") or normalize_name_key(rec.get("person_name", ""), rec.get("company", ""))
        if nk and len(nk) > 3:
            self.seen_names.add(nk)

        prop = rec.get("property_address")
        if prop:
            clean_prop = re.sub(r"[^a-zA-Z0-9]", "", str(prop)).lower()
            if len(clean_prop) > 5:
                self.seen_properties.add(clean_prop)

        lid = rec.get("lead_id")
        if lid:
            self.seen_lead_ids.add(lid)

    def is_historically_seen(
        self,
        phone: str = "",
        email: str = "",
        company: str = "",
        contact: str = "",
        property_address: str = "",
        lead_id: str = "",
    ) -> Tuple[bool, str]:
        """
        Check if a lead has ever been seen in the historical ledger.
        Returns (is_seen, reason).
        """
        norm_p = normalize_phone_digits(phone)
        if norm_p and norm_p in self.seen_phones:
            return True, f"Phone {norm_p} already exists in historical ledger"

        norm_e = normalize_email_address(email)
        if norm_e and norm_e in self.seen_emails:
            return True, f"Email {norm_e} already exists in historical ledger"

        if contact and company:
            nk = normalize_name_key(contact, company)
            if nk and nk in self.seen_names:
                return True, f"Contact+Company identity '{contact} @ {company}' already in historical ledger"

        if property_address:
            clean_prop = re.sub(r"[^a-zA-Z0-9]", "", str(property_address)).lower()
            if clean_prop and clean_prop in self.seen_properties:
                return True, f"Property address '{property_address}' already in historical ledger"

        if lead_id and lead_id in self.seen_lead_ids:
            return True, f"Lead ID {lead_id} already in historical ledger"

        return False, ""

    def register_lead(
        self,
        lead: Dict[str, Any],
        batch_date: Optional[str] = None,
        status: str = "VERIFIED_ACTIVE",
        batch_id: str = "daily-production",
    ) -> Dict[str, Any]:
        """Register or update a lead in the historical ledger."""
        now_date = batch_date or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        now_iso = datetime.now(timezone.utc).isoformat()

        phone = lead.get("phone") or lead.get("contact_phone") or ""
        norm_p = normalize_phone_digits(phone)
        email = lead.get("email") or lead.get("contact_email") or ""
        norm_e = normalize_email_address(email)
        contact = lead.get("contact") or lead.get("decision_maker") or lead.get("owner_name") or ""
        company = lead.get("company") or lead.get("company_name") or ""
        lead_id = lead.get("id") or lead.get("lead_id") or f"LEAD-{norm_p or 'GEN'}"
        prop_addr = lead.get("property_address") or lead.get("address") or ""

        identity_key = f"phone:{norm_p}" if norm_p else f"id:{lead_id}"

        existing = self.records.get(identity_key)
        first_seen = existing.get("first_seen_date", now_date) if existing else now_date

        rec = {
            "identity_key": identity_key,
            "lead_id": lead_id,
            "phone": f"+1{norm_p}" if norm_p else phone,
            "norm_phone": norm_p,
            "email": email,
            "norm_email": norm_e,
            "company": company,
            "person_name": contact,
            "name_key": normalize_name_key(contact, company),
            "property_address": prop_addr,
            "source": lead.get("source", "Directory Signal"),
            "source_reference": lead.get("source_reference", ""),
            "status": status,
            "first_seen_date": first_seen,
            "last_seen_date": now_date,
            "batch_id": batch_id,
            "last_updated_at": now_iso,
        }

        self.records[identity_key] = rec
        self._index_record(rec)
        return rec

    def save(self) -> None:
        """Persist ledger to disk."""
        data = list(self.records.values())
        self.ledger_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def bootstrap_from_existing_data(self) -> int:
        """
        Bootstrap the historical ledger from current leads_database.json,
        canonical_deals_memory.json, and existing daily history files.
        """
        bootstrapped_count = 0
        now_date = "2026-08-15"  # Mark existing pre-today inventory as historical

        # 1. Ingest existing dialer database (762 leads)
        dialer_db = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"
        if dialer_db.exists():
            try:
                dialer_leads = json.loads(dialer_db.read_text(encoding="utf-8"))
                for d in dialer_leads:
                    self.register_lead(
                        d,
                        batch_date=now_date,
                        status="ACTIVE_DIALER",
                        batch_id="historical-bootstrap-dialer",
                    )
                    bootstrapped_count += 1
            except Exception as e:
                print(f"[WARN] Failed bootstrapping from dialer db: {e}")

        # 2. Ingest canonical deals memory
        canon_db = ROOT_DIR / "MBM" / "Artifacts" / "canonical_deals_memory.json"
        if canon_db.exists():
            try:
                canon_deals = json.loads(canon_db.read_text(encoding="utf-8"))
                for deal in canon_deals:
                    self.register_lead(
                        deal,
                        batch_date=now_date,
                        status=deal.get("stage", "QUALIFIED"),
                        batch_id="historical-bootstrap-canonical",
                    )
                    bootstrapped_count += 1
            except Exception as e:
                print(f"[WARN] Failed bootstrapping from canonical memory: {e}")

        # 3. Ingest daily lead factory history if exists
        hist_db = ROOT_DIR / "MBM" / "Artifacts" / "daily_lead_factory_history.json"
        if hist_db.exists():
            try:
                hist_leads = json.loads(hist_db.read_text(encoding="utf-8"))
                for h in hist_leads:
                    self.register_lead(
                        h,
                        batch_date=now_date,
                        status="HISTORICAL_EXPORT",
                        batch_id="historical-bootstrap-history",
                    )
                    bootstrapped_count += 1
            except Exception as e:
                print(f"[WARN] Failed bootstrapping from history db: {e}")

        self.save()
        print(f"[OK] LeadHistoryLedger bootstrapped with {len(self.records)} unique historical identities ({len(self.seen_phones)} unique phones).")
        return len(self.records)

    def stats(self) -> Dict[str, Any]:
        """Return ledger summary statistics."""
        return {
            "total_records": len(self.records),
            "unique_phones": len(self.seen_phones),
            "unique_emails": len(self.seen_emails),
            "unique_identities": len(self.seen_names),
            "unique_properties": len(self.seen_properties),
        }


if __name__ == "__main__":
    ledger = LeadHistoryLedger()
    st = ledger.stats()
    print("=" * 70)
    print("MBM PERMANENT HISTORICAL EXCLUSION LEDGER STATUS")
    print(f"Total Unique Historical Identities: {st['total_records']}")
    print(f"Indexed Callable Phones:            {st['unique_phones']}")
    print(f"Indexed Direct Emails:              {st['unique_emails']}")
    print(f"Indexed Business Identities:        {st['unique_identities']}")
    print("=" * 70)
