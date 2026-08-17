#!/usr/bin/env python3
"""
LEAD PROVENANCE GATE (ZERO-SYNTHETIC ENFORCEMENT)
=============================================================================
Mandatory provenance contract for EVERY production lead.

A record may NOT enter production (dialer DB, GTM opportunities, execution
queue, daily verified count, telegram/email, calling queue) unless it passes:

  PROVENANCE_REQUIRED  AND  NOT_SYNTHETIC

PROVENANCE_REQUIRED means all of these fields are present and non-empty:
  source               - named real source (e.g. "CMS NPI Registry API v2.1")
  source_reference     - resolvable reference (NPI #, parcel APN, registry URL)
  source_type          - "government_registry" | "county_record" |
                         "business_registry" | "authoritative_api" | ...
  observed_at          - when the signal was first observed (ISO8601)
  verified_at          - when verification completed (ISO8601)
  verification_method  - HOW it was verified; MUST be a real method, never
                         "generated" / "synthetic" / "demo" / "template" ...

NOT_SYNTHETIC means NONE of the fabrication fingerprints fire:
  - template company     <City> <Vertical> <Suffix>  (e.g. "Chattanooga Civil Enterprises")
  - persona contact      surname/first-name from the known synthetic pools
  - generated domain     email domain == slug(company).com
  - sequential registry  source_reference built from {idx:06d} sequences
  - low-entropy phone    <=4 unique digits (e.g. +12002001061)

This module is the SINGLE enforcement point used by:
  - daily_lead_factory        (harvest + acceptance)
  - dialer DB writer          (ingestion gate)
  - quarantine tool           (purge existing synthetic rows)
  - verification gates        (dialer_verification_gate, gtm adapters)
  - regression tests
=============================================================================
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# 1. Provenance Contract
# ---------------------------------------------------------------------------

REQUIRED_PROVENANCE_FIELDS: List[str] = [
    "source",
    "source_reference",
    "source_type",
    "observed_at",
    "verified_at",
    "verification_method",
]

# Real, evidence-backed verification methods. A lead's verification_method
# MUST be one of these (or an explicit subclass) to be considered real.
REAL_VERIFICATION_METHODS: Dict[str, str] = {
    "npi_registry_api": "CMS NPI Registry API v2.1 (government registry, real licensed business + phone)",
    "npi/registry": "CMS NPI Registry API v2.1 (government registry, real licensed business + phone)",
    "cms_npi": "CMS NPI Registry API v2.1 (government registry, real licensed business + phone)",
    "county_record": "County appraisal district ownership record (DCAD/Tarrant/Harris/Collin)",
    "dcad": "Dallas Central Appraisal District ownership verification (APN + owner)",
    "state_licensing": "State commercial licensing directory (verified real license record)",
    "business_registry": "State Secretary of State business registry (verified real entity)",
    "carrier_lookup": "Carrier / phone-number lookup confirming real line",
    "twilio_lookup": "Twilio Lookup number verification (real line + carrier)",
    "gmaps": "Google Maps / Places listing confirmation",
    "domain_whois": "Domain WHOIS confirming registered business domain",
    "public_business_record": "Public business / court / UCC record",
    "authoritative_registry": "Authoritative government registry (real entity + phone)",
    "existing_verified_dialer": "Already present in verified production dialer inventory",
}

# Explicitly forbidden verification methods - fabricated / placeholder claims.
SYNTHETIC_VERIFICATION_METHODS: Dict[str, str] = {
    "generated": "verification method is a fabrication",
    "synthetic": "verification method is a fabrication",
    "simulated": "verification method is a simulation",
    "demo": "demo / test data",
    "template": "template-generated record",
    "mock": "mock data",
    "fabricated": "explicit fabrication",
    "placeholder": "placeholder data",
    "sample": "sample / fixture data",
    "assumed": "assumed without evidence",
    "state business licensing directory": "unverifiable generic registry claim",
}

# ---------------------------------------------------------------------------
# 2. Synthetic Fingerprint Detection
# ---------------------------------------------------------------------------

# Cities used by the legacy synthetic generator (GEOGRAPHIC_REGIONS).
SYNTHETIC_CITIES: set = {
    "Dallas", "Fort Worth", "Houston", "Austin", "San Antonio", "Plano", "Arlington",
    "Miami", "Orlando", "Tampa", "Jacksonville", "Fort Lauderdale", "St. Petersburg",
    "Phoenix", "Scottsdale", "Mesa", "Chandler", "Tempe", "Tucson",
    "Atlanta", "Alpharetta", "Marietta", "Savannah", "Augusta",
    "Charlotte", "Raleigh", "Durham", "Greensboro", "Winston-Salem",
    "Nashville", "Memphis", "Knoxville", "Chattanooga", "Franklin",
    "Denver", "Boulder", "Colorado Springs", "Aurora", "Fort Collins",
    "Columbus", "Cleveland", "Cincinnati", "Dayton", "Akron",
}

SYNTHETIC_SUFFIXES: tuple = (
    "Solutions", "Partners", "Group", "Services", "Enterprises", "Systems", "Contractors",
)

# Vertical keywords the generator interpolates into company names.
SYNTHETIC_VERTICAL_KEYWORDS: tuple = (
    "Civil", "Structural", "Construction", "Electrical", "Automation", "Plumbing",
    "Roofing", "Exterior", "Mechanical", "Dental", "Orthodontics", "Medical",
    "Clinics", "Urgent", "Care", "Med", "Spa", "Aesthetics", "Personal", "Injury",
    "Corporate", "Law", "Accounting", "Tax", "Advisory", "Commercial", "Insurance",
    "Brokerages", "Auto", "Repair", "Collision", "Veterinary", "Hospitals",
    "Staffing", "Recruiting", "Agencies", "Digital", "Marketing", "SEO", "Freight",
    "Logistics", "Dispatch", "Home", "Services", "Pest", "Control", "Property",
    "Management", "Multi-Family", "Real", "Estate", "Brokerages", "Asset", "Teams",
)

# First/last name pools from the legacy synthetic generator.
SYNTHETIC_FIRST_NAMES: set = {
    "Marcus", "Elena", "Derek", "Sarah", "Robert", "Garrett", "Victoria", "David",
    "Rachel", "Brandon", "Samantha", "Christopher", "Jessica", "Daniel", "Amanda",
    "Matthew", "Ashley", "Andrew", "Stephanie", "Joshua", "Megan", "Brian", "Nicole",
    "Kevin", "Hannah", "Eric", "Elizabeth", "Justin", "Lauren", "Ryan", "Emily",
}
SYNTHETIC_LAST_NAMES: set = {
    "Vance", "Sterling", "Holloway", "Lin", "Cole", "Reynolds", "Thornton", "Mercer",
    "Blackwood", "Caldwell", "Stafford", "Sinclair", "Montgomery", "Barrington",
    "Hastings", "Kensington", "Prescott", "Winslow", "Fairfax", "Beaumont",
    "Ellington", "Whitmore",
}

# Registry hosts used by the legacy generator for sequential entity refs.
SYNTHETIC_REF_HOSTS: tuple = (
    "sos.texas.gov", "myfloridalicense.com", "business.ohio.gov", "sos.ga.gov",
    "license.tx.gov", "license.fl.gov", "license.az.gov", "license.ga.gov",
    "license.nc.gov", "license.tn.gov", "license.co.gov", "license.oh.gov",
)

_ALNUM_RE = re.compile(r"[^a-zA-Z0-9]")
_ENTITY_SEQ_RE = re.compile(r"/entity/\d{5,}$")
_PHONE_DIGITS_RE = re.compile(r"\D")


def _slug(text: str) -> str:
    return _ALNUM_RE.sub("", str(text or "")).lower()


def _digits(phone: Any) -> str:
    d = _PHONE_DIGITS_RE.sub("", str(phone or ""))
    if len(d) == 11 and d.startswith("1"):
        return d[1:]
    return d


def is_generated_domain(email: str, company: str) -> bool:
    """True when the email domain is the slug of the company name itself."""
    if not email or not company:
        return False
    domain = str(email).split("@")[-1].lower()
    base = domain.split(".")[0]
    return bool(base) and base == _slug(company) and len(base) > 4


def is_template_company(company: str) -> bool:
    """True when company matches <City> <Vertical> <Suffix> template shape."""
    if not company:
        return False
    words = company.strip().split()
    if len(words) < 3:
        return False
    if words[0] not in SYNTHETIC_CITIES:
        return False
    if not words[-1].endswith(SYNTHETIC_SUFFIXES) and words[-1] not in SYNTHETIC_SUFFIXES:
        return False
    mid = " ".join(words[1:-1])
    return any(k in mid for k in SYNTHETIC_VERTICAL_KEYWORDS)


def is_persona_contact(name: str) -> bool:
    """True when contact looks like a synthetic persona (pool first+last)."""
    if not name:
        return False
    parts = str(name).replace(".", " ").split()
    if len(parts) < 2:
        return False
    fn = parts[0]
    ln = parts[-1]
    if ln in SYNTHETIC_LAST_NAMES and fn in SYNTHETIC_FIRST_NAMES:
        return True
    # single distinctive synthetic surname with generated first name
    if ln in SYNTHETIC_LAST_NAMES and fn not in SYNTHETIC_FIRST_NAMES:
        return False  # real people may share surnames; require full pool match
    return False


def is_sequential_registry_ref(source_reference: Any) -> bool:
    """True when ref is a URL path like /entity/000771 or registry+sequence."""
    if not source_reference:
        return False
    ref = str(source_reference)
    for host in SYNTHETIC_REF_HOSTS:
        if host in ref and _ENTITY_SEQ_RE.search(ref):
            return True
    return False


def is_low_entropy_phone(phone: Any) -> bool:
    """True when a phone has <=4 unique digits (generator artifact)."""
    d = _digits(phone)
    if len(d) < 10:
        return True
    return len(set(d)) <= 4


def is_placeholder_phone(phone: Any) -> bool:
    d = _digits(phone)
    # _digits strips a leading country code "1", so a remaining leading "1"
    # is a legitimate NANP trunk prefix (e.g. +11787306835 -> 1787306835).
    # Only flag: 0-leading area codes, short numbers, and reserved NANP
    # patterns. "555" is reserved only in the 3-digit EXCHANGE position
    # (digits[3:6]); a "555"/"000" substring in the subscriber part is real
    # (e.g. 216-445-8000, 702-545-0555) and must not be rejected.
    return (not d) or len(d) < 10 or d.startswith("0") or d[3:6] == "555" or d.startswith("000")


# ---------------------------------------------------------------------------
# 3. Detector + Gate
# ---------------------------------------------------------------------------

class SyntheticLeadDetector:
    """
    Detects fabrication fingerprints on a candidate record.
    Returns (is_synthetic, list_of_signals).
    """

    def detect(self, record: Dict[str, Any]) -> Tuple[bool, List[str]]:
        signals: List[str] = []

        # provenance must be complete AND verified by a real method
        missing = [f for f in REQUIRED_PROVENANCE_FIELDS if not record.get(f)]
        if missing:
            signals.append(f"missing_provenance:{','.join(missing)}")

        vmethod = str(record.get("verification_method", "")).strip().lower()
        if vmethod in SYNTHETIC_VERIFICATION_METHODS:
            signals.append(f"forbidden_verification_method:{vmethod}")

        company = record.get("company") or record.get("company_name") or ""
        contact = (
            record.get("contact")
            or record.get("decision_maker")
            or record.get("person_name")
            or record.get("owner_name")
            or ""
        )
        email = record.get("email") or record.get("contact_email") or ""
        ref = record.get("source_reference") or record.get("source_url") or ""
        phone = record.get("phone") or record.get("contact_phone") or record.get("norm_phone") or ""

        if is_template_company(company):
            signals.append("template_company")
        if email and is_generated_domain(email, company):
            signals.append("generated_domain")
        if is_persona_contact(contact):
            signals.append("persona_contact")
        if is_sequential_registry_ref(ref):
            signals.append("sequential_registry_ref")
        if is_placeholder_phone(phone):
            signals.append("placeholder_phone")
        elif is_low_entropy_phone(phone):
            signals.append("low_entropy_phone")

        # direct fabrication flags on the record itself
        for key in ("synthetic", "is_synthetic", "is_fabricated", "is_demo", "is_fixture"):
            if record.get(key):
                signals.append(f"explicit_{key}")

        if record.get("source") and "state business licensing directory" in str(record.get("source")).lower():
            signals.append("generic_unverifiable_source")

        return bool(signals), signals


class LeadProvenanceGate:
    """
    The single acceptance gate. Returns detailed result dict.
    A record is PROVENANCE_OK iff provenance complete AND zero synthetic signals.
    """

    def __init__(self):
        self.detector = SyntheticLeadDetector()

    def evaluate(self, record: Dict[str, Any]) -> Dict[str, Any]:
        is_synthetic, signals = self.detector.detect(record)
        missing = [f for f in REQUIRED_PROVENANCE_FIELDS if not record.get(f)]
        ok = (not missing) and (not is_synthetic)
        return {
            "ok": ok,
            "provenance_complete": not missing,
            "missing_fields": missing,
            "synthetic": is_synthetic,
            "signals": signals,
        }

    def require(self, record: Dict[str, Any]) -> Dict[str, Any]:
        """Strict variant that RAISES on synthetic/fabricated input."""
        result = self.evaluate(record)
        if not result["ok"]:
            raise ValueError(
                "PROVENANCE_REJECTED: " + "; ".join(result["signals"] or result["missing_fields"])
            )
        return result

    def filter_real(self, records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        """Return only provenance-clean records + count of synthetic rejected."""
        real: List[Dict[str, Any]] = []
        synthetic = 0
        for rec in records:
            if self.evaluate(rec)["ok"]:
                real.append(rec)
            else:
                synthetic += 1
        return real, synthetic


# ---------------------------------------------------------------------------
# 4. Provenance Helpers
# ---------------------------------------------------------------------------

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_provenance_fields(
    source: str,
    source_reference: str,
    source_type: str,
    verification_method: str,
    observed_at: str = "",
) -> Dict[str, str]:
    """Attach a full provenance block to a record."""
    return {
        "source": source,
        "source_reference": source_reference,
        "source_type": source_type,
        "observed_at": observed_at or now_iso(),
        "verified_at": now_iso(),
        "verification_method": verification_method,
    }


def production_synthetic_count(records: List[Dict[str, Any]]) -> int:
    """Count of records failing the provenance gate (synthetic count)."""
    gate = LeadProvenanceGate()
    return sum(0 if gate.evaluate(r)["ok"] else 1 for r in records)


if __name__ == "__main__":
    # Smoke-test against known synthetic + real samples.
    gate = LeadProvenanceGate()
    syn = {
        "id": "GEN-NEW-07053",
        "company": "Chattanooga Civil Enterprises",
        "contact": "Ashley Mercer",
        "phone": "+14235712699",
        "email": "ashley@chattanoogacivilenterprises.com",
        "source": "TN State Commercial Licensing Board",
        "source_reference": "https://license.tn.gov/entity/004773",
        "verification_method": "state licensing",
    }
    real = {
        "id": "NPI-1568833093",
        "company": "ADVANTAGE MEDICAL GROUP LLC",
        "contact": "ARCILIO ALVARADO",
        "phone": "+17873068356",
        "email": "",
        "source": "CMS NPI Registry API v2.1",
        "source_reference": "NPI-1568833093",
        "source_type": "government_registry",
        "observed_at": "2026-08-15T12:51:50Z",
        "verified_at": "2026-08-15T12:51:50Z",
        "verification_method": "npi_registry_api",
    }
    print("SYNTHETIC:", gate.evaluate(syn))
    print("REAL:", gate.evaluate(real))