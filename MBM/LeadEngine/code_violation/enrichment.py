"""enrichment -- property -> owner -> phone for code-violation leads.

Owner:
  - Dallas County parcels    -> MBM.LeadEngine.dcad_owner_lookup (fast, authoritative)
  - other counties (Tarrant, Collin) -> property_intel CountyRoutedVerifier
                                      (verified ArcGIS county assessor adapters)

Phone:
  - FreeSkipTracer.find_contact(owner, address, city) - the existing authorized
    enrichment rail. Numbers must pass NANP + placeholder + suppression checks.

Nothing is ever invented: no owner -> no phone. Unverified property stays
with owner_status VERIFICATION_REQUIRED / NOT_FOUND and is never forced.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from ..dcad_owner_lookup import dcad_lookup
from ..free_skip_tracer import FreeSkipTracer
from ..lead_provenance import is_placeholder_phone
from ..property_intel.ownership_verifier import verify_ownership

DEFAULT_COUNTY = "Dallas"


def county_for_city(city: str) -> str:
    mapping = {
        "dallas": "Dallas",
        "irving": "Dallas",
        "garland": "Dallas",
        "mesquite": "Dallas",
        "fort worth": "Tarrant",
        "arlington": "Tarrant",
        "plano": "Collin",
    }
    return mapping.get(str(city or "").strip().lower(), DEFAULT_COUNTY)


@dataclass
class OwnerResult:
    owner_name: str
    parcel_id: str
    owner_status: str
    confidence: float
    mail_city: str
    mail_state: str
    source: str
    source_url: str
    evidence: list
    absentee: Optional[bool] = None

    def to_dict(self) -> dict:
        return {
            "owner_name": self.owner_name,
            "parcel_id": self.parcel_id,
            "owner_status": self.owner_status,
            "confidence": self.confidence,
            "mail_city": self.mail_city,
            "mail_state": self.mail_state,
            "source": self.source,
            "source_url": self.source_url,
            "evidence": self.evidence,
            "absentee": self.absentee,
        }


def resolve_owner(
    rec: dict,
    live: bool = True,
    dcad_fn: Optional[Any] = None,
    verify_fn: Optional[Any] = None,
) -> OwnerResult:
    """Resolve the legal owner for a violation record. Never invents."""
    county = rec.get("county") or county_for_city(rec.get("city", ""))
    address = str(rec.get("address", "") or "").strip()
    parcel = str(rec.get("parcel_id", "") or "").strip()

    if not address and not parcel:
        return OwnerResult("", "", "NOT_FOUND", 0.0, "", "", "none", "", [])

    if county == "Dallas":
        look = (dcad_fn or dcad_lookup)(address) if address else None
        if look and look.get("error"):
            return OwnerResult("", parcel, "NOT_FOUND", 0.0, "", "", "dcad", "", [])
        if look and look.get("owner"):
            owner = str(look.get("owner")).strip()
            pcl = str(look.get("parcel_id") or "").strip()
            status = "VERIFIED"
            conf = 0.9
            mail_city = str(look.get("mail_city") or "").strip()
            mail_state = str(look.get("mail_state") or "").strip()
            absentee = _absentee_check(
                mail_state or mail_city,
                rec.get("city", ""),
                rec.get("state", ""),
            )
            return OwnerResult(
                owner_name=owner,
                parcel_id=pcl,
                owner_status=status,
                confidence=conf,
                mail_city=mail_city,
                mail_state=mail_state,
                source="DCAD",
                source_url="https://maps.dcad.org/prdwa/rest/services/Property/ParcelQuery/MapServer/4",
                evidence=[{"source": "DCAD", "claim": f"Parcel {pcl or 'n/a'} registered to {owner}"}],
                absentee=absentee,
            )
        return OwnerResult("", parcel, "NOT_FOUND", 0.0, "", "", "dcad", "", [])

    verify = verify_fn or (lambda r: verify_ownership(r, live=live))
    result = verify({
        "state": rec.get("state", ""),
        "county": county,
        "city": rec.get("city", ""),
        "address": address,
        "parcel_id": parcel,
    })
    if result is None:
        return OwnerResult("", parcel, "REQUIRES_VERIFICATION", 0.0, "", "", county, "", [])
    status = str(result.verification_status or "NOT_FOUND")
    owner = str(result.owner_name or "").strip()
    conf = float(result.confidence or 0.0)
    ev = [e.to_dict() if hasattr(e, "to_dict") else str(e) for e in (result.evidence or [])]
    mail_where = (
        getattr(result, "mail_state", None)
        or getattr(result, "mail_city", None)
        or str(result.mailing_address or "")
    )
    absentee = _absentee_check(
        str(mail_where or ""),
        rec.get("city", ""),
        rec.get("state", ""),
    )
    return OwnerResult(
        owner_name=owner,
        parcel_id=str(result.parcel_id or parcel or "").strip(),
        owner_status=status,
        confidence=conf,
        mail_city=str(getattr(result, "mail_city", "") or ""),
        mail_state=str(getattr(result, "mail_state", "") or ""),
        source=str(result.source or county),
        source_url=str(result.source_url or ""),
        evidence=ev,
        absentee=absentee,
    )


def _absentee_check(mail_where: str, site_city: str, site_state: str) -> Optional[bool]:
    """Absentee = owner mailing address is in a different state than the
    property. Returns None when we cannot tell (never guessed)."""
    if not mail_where or not site_state:
        return None
    mail_l = mail_where.strip().lower()
    site_state_l = site_state.strip().lower()
    mail_state = mail_l.split(",")[-1].strip().split()[-1] if "," in mail_l else mail_l.split()[-1]
    if mail_state == site_state_l:
        return False
    return True


@dataclass
class PhoneResult:
    phone: str
    source: str
    confidence: float
    email: str
    status: str  # OK | NO_PHONE | REJECTED

    def to_dict(self) -> dict:
        return {
            "phone": self.phone,
            "source": self.source,
            "confidence": self.confidence,
            "email": self.email,
            "status": self.status,
        }


def _valid_nanp(phone: str) -> bool:
    digits = re.sub(r"\D", "", phone or "")
    return len(digits) == 10 or (len(digits) == 11 and digits.startswith("1"))


def enrich_phone(
    owner: OwnerResult,
    rec: dict,
    skip_tracer: Optional[FreeSkipTracer] = None,
    suppression: Optional[set] = None,
) -> PhoneResult:
    """Skip-trace the owner for a callable phone. No owner -> no phone."""
    if not owner.owner_name or owner.owner_status not in ("VERIFIED", "LIKELY"):
        return PhoneResult("", "", 0.0, "", "NO_PHONE")
    tracer = skip_tracer or FreeSkipTracer()
    address = str(rec.get("address", "") or "").strip()
    city = str(rec.get("city", "") or "").strip()
    try:
        contact = tracer.find_contact(owner.owner_name, address, city)
    except Exception:  # noqa: BLE001 - enrichment must never kill the pipeline
        return PhoneResult("", "", 0.0, "", "NO_PHONE")
    if not contact:
        return PhoneResult("", "", 0.0, "", "NO_PHONE")
    phone = str(contact.get("phone") or "").strip()
    conf_raw = str(contact.get("confidence") or "").lower()
    conf = 0.6 if conf_raw in ("high", "medium", "medium-high") else 0.3
    if not phone or not _valid_nanp(phone) or is_placeholder_phone(phone):
        return PhoneResult("", "", 0.0, "", "NO_PHONE")
    digits = re.sub(r"\D", "", phone)
    digits = digits[-10:]
    if suppression and digits in suppression:
        return PhoneResult("", "", 0.0, "", "REJECTED")
    return PhoneResult(
        phone=f"+1{digits}",
        source=str(contact.get("source") or "free_skip_tracer"),
        confidence=conf,
        email=str(contact.get("email") or "").strip(),
        status="OK",
    )
