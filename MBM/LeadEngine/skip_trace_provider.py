"""SkipTraceProvider - normalized skip-trace provider abstraction (P0 P4).

Law:
- Providers are replaceable adapters behind one interface. The dialer is never
  hard-coded to one vendor.
- Adapters may ONLY use official APIs, authorized exports, or approved
  integrations. No scraping of protected systems, no leaked credentials.
- A provider that is not connected reports available()=False and is skipped.
- Results are evidence records, not truths: every field carries provenance and
  the consensus engine + identity gate decide promotability.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class SkipTraceResult:
    """Standard output schema for every provider adapter."""

    lead_id: str
    property_address: str
    owner_name: str
    candidate_phone: str
    phone_type: str  # mobile | landline | voip | unknown
    provider: str
    provider_confidence: float  # 0..1 vendor-stated confidence
    owner_match: str  # MATCH | PARTIAL | NO_MATCH | UNKNOWN
    address_match: str  # MATCH | PARTIAL | NO_MATCH | UNKNOWN
    source_timestamp: str  # when provider sourced the record
    verification_timestamp: str  # when we fetched it
    dnc_status: str  # DNC | LITIGATOR | CLEAR | UNKNOWN
    litigator_status: str = "UNKNOWN"
    raw_reference: str = ""  # provider record id / request ref for audit
    evidence: dict = field(default_factory=dict)

    def to_phone_candidate(self):
        """Convert into a PhoneCandidate for PhoneConsensusEngine."""
        from MBM.LeadEngine.contact_verification_pipeline import PhoneCandidate

        conf = max(0.0, min(1.0, float(self.provider_confidence)))
        return PhoneCandidate(
            phone=self.candidate_phone,
            owner_match=1.0 if self.owner_match == "MATCH"
            else (0.5 if self.owner_match == "PARTIAL" else 0.0),
            address_match=1.0 if self.address_match == "MATCH"
            else (0.5 if self.address_match == "PARTIAL" else 0.0),
            sources=[f"provider:{self.provider}"],
            line_type=self.phone_type,
            last_verified_at=self.source_timestamp or _iso_now(),
            source_reliability=conf,
            dnc=self.dnc_status in ("DNC", "LITIGATOR"),
            litigator=(self.litigator_status == "LITIGATOR"),
        )

    def to_dict(self) -> dict:
        return asdict(self)


class SkipTraceProvider(ABC):
    """Base class every adapter must implement."""

    name: str = "abstract"
    cost_per_record_usd: float = 0.0

    @abstractmethod
    def available(self) -> bool:
        """True only when real credentials/access exist right now."""

    @abstractmethod
    def trace(self, lead: dict) -> list[SkipTraceResult]:
        """Return candidate results for one lead dict. NEVER fabricates."""

    def describe(self) -> dict:
        return {"name": self.name, "cost_per_record_usd": self.cost_per_record_usd,
                "available": self.available()}


class NullProvider(SkipTraceProvider):
    """Registered fallback when no paid provider is connected."""

    name = "null"

    def available(self) -> bool:
        return False

    def trace(self, lead: dict) -> list[SkipTraceResult]:
        return []


class InternalHistoryProvider(SkipTraceProvider):
    """Free internal source: re-surfaces phones already on the lead plus any
    alternates recorded in its own history/quarantine. Owner/address match is
    asserted ONLY from existing verified fields; otherwise UNKNOWN."""

    name = "internal_history"

    def available(self) -> bool:
        return True

    def trace(self, lead: dict) -> list[SkipTraceResult]:
        details = lead.get("details") or {}
        owner = lead.get("owner_name") or details.get("owner_name") or ""
        addr = lead.get("address") or lead.get("property_address") or ""
        owner_verified = (lead.get("owner_verification_status")
                          or details.get("owner_verification_status") or "")
        out: list[SkipTraceResult] = []
        primary = normalize(lead.get("phone"))
        if primary:
            out.append(SkipTraceResult(
                lead_id=lead.get("id", ""), property_address=addr, owner_name=owner,
                candidate_phone=primary,
                phone_type=(lead.get("phone_type") or "unknown"),
                provider=self.name, provider_confidence=0.3,
                owner_match=("MATCH" if owner_verified in
                             ("VERIFIED_OWNER", "VERIFIED") else "UNKNOWN"),
                address_match=("MATCH" if details.get("county_parcel_verified")
                               else "UNKNOWN"),
                source_timestamp=str(lead.get("added_at") or ""),
                verification_timestamp=_iso_now(),
                dnc_status=("DNC" if _is_dnc(lead) else "CLEAR"),
                raw_reference=f"lead:{lead.get('id', '')}",
                evidence={"origin": "existing_lead_phone"},
            ))
        for alt in (lead.get("alternate_phones") or [])[:5]:
            phone = normalize(alt.get("phone") if isinstance(alt, dict) else alt)
            if phone and phone != primary:
                out.append(SkipTraceResult(
                    lead_id=lead.get("id", ""), property_address=addr, owner_name=owner,
                    candidate_phone=phone, phone_type="unknown",
                    provider=self.name, provider_confidence=0.2,
                    owner_match="UNKNOWN", address_match="UNKNOWN",
                    source_timestamp=str(alt.get("ts", "")) if isinstance(alt, dict) else "",
                    verification_timestamp=_iso_now(),
                    dnc_status="CLEAR", raw_reference=f"lead:{lead.get('id', '')}:alt",
                    evidence={"origin": "lead_history"},
                ))
        return out


def normalize(phone: Any) -> str:
    if not phone:
        return ""
    digits = "".join(c for c in str(phone) if c.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return f"+1{digits}" if len(digits) == 10 else ""


def _is_dnc(lead: dict) -> bool:
    return bool(lead.get("dnc") or lead.get("dnd")
                or (lead.get("details") or {}).get("dnc"))


PROVIDER_REGISTRY: dict[str, type[SkipTraceProvider]] = {
    InternalHistoryProvider.name: InternalHistoryProvider,
    NullProvider.name: NullProvider,
}

# Future adapters register here once credentials exist (Phase 3 gate):
#   PropStreamProvider, DealMachineProvider, BatchProvider, ...


def get_provider(name: str) -> SkipTraceProvider:
    cls = PROVIDER_REGISTRY.get(name)
    if cls is None:
        raise KeyError(f"unknown provider '{name}'")
    return cls()


def first_available_provider() -> SkipTraceProvider | None:
    for name in PROVIDER_REGISTRY:
        p = get_provider(name)
        if p.available():
            return p
    return None
