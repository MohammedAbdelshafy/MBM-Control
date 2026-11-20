"""Provider-neutral ingestion controls for acquisition data sources.

This module normalizes already-retrieved provider payloads into MBM's existing
EvidenceEnvelope. It does not search, enrich, export, send, or write to a lead
store. Contact-level fields are withheld unless the caller explicitly allows
the exact fields for the current data operation.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from MBM.LeadEngine.connectors.evidence import EvidenceEnvelope, build_evidence


PROVIDER_ALIASES = {
    "VIBE": "VIBE_PROSPECTING",
    "AI_VIBE_PROSPECTING": "VIBE_PROSPECTING",
    "VIBE_PROSPECTING": "VIBE_PROSPECTING",
    "APOLLO_IO": "APOLLO",
    "APOLLO": "APOLLO",
    "CLAY": "CLAY",
    "ZOOMINFO": "ZOOMINFO",
    "LINKEDIN": "LINKEDIN",
    "CMS": "CMS_NPPES",
    "NPPES": "CMS_NPPES",
    "CMS_NPPES": "CMS_NPPES",
    "PUBLIC_RECORDS": "OFFICIAL_RECORDS",
    "OFFICIAL_RECORDS": "OFFICIAL_RECORDS",
    "COUNTY_RECORDS": "OFFICIAL_RECORDS",
    "MANUAL": "MANUAL",
}

CONTACT_FIELDS = frozenset({
    "person_name",
    "contact_name",
    "decision_maker_name",
    "owner_name",
    "email",
    "email_address",
    "work_email",
    "personal_email",
    "owner_email",
    "phone",
    "phone_number",
    "mobile",
    "mobile_phone",
    "direct_dial",
    "direct_phone",
    "owner_phone",
    "owner_mobile",
    "person_linkedin_url",
    "contact_linkedin_url",
})


@dataclass(frozen=True)
class ProviderIngestResult:
    envelope: EvidenceEnvelope
    included_fields: tuple[str, ...]
    withheld_contact_fields: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        return {
            "envelope": self.envelope.as_dict(),
            "included_fields": list(self.included_fields),
            "withheld_contact_fields": list(self.withheld_contact_fields),
        }


def normalize_provider_record(
    *,
    lead_id: str,
    provider: str,
    claims: Mapping[str, Any],
    source: str,
    confidence: str = "UNKNOWN",
    reference: str | None = None,
    observed_at: str | None = None,
    approved_contact_fields: Iterable[str] = (),
) -> ProviderIngestResult:
    """Convert provider claims to evidence with an exact-field contact gate.

    approved_contact_fields must come from an explicit authorization check in
    the calling workflow. It never grants permission to export, contact, or
    promote a record into a callable queue.
    """
    provider_key = str(provider or "").strip().upper()
    canonical_provider = PROVIDER_ALIASES.get(provider_key)
    if not canonical_provider:
        raise ValueError(f"unsupported acquisition provider: {provider_key or 'UNKNOWN'}")
    if not isinstance(claims, Mapping):
        raise ValueError("claims must be a mapping")

    approved = {
        str(field).strip().lower()
        for field in approved_contact_fields
        if str(field).strip()
    }
    included: dict[str, Any] = {}
    withheld: list[str] = []

    for raw_field, value in claims.items():
        field_name = str(raw_field).strip()
        if not field_name or value is None:
            continue
        normalized_field = field_name.lower()
        if normalized_field in CONTACT_FIELDS and normalized_field not in approved:
            withheld.append(field_name)
            continue
        included[field_name] = value

    envelope = build_evidence(
        lead_id=lead_id,
        provider=canonical_provider,
        claims=included,
        source=source,
        confidence=confidence,
        reference=reference,
        observed_at=observed_at,
    )
    return ProviderIngestResult(
        envelope=envelope,
        included_fields=tuple(sorted(included)),
        withheld_contact_fields=tuple(sorted(withheld)),
    )
