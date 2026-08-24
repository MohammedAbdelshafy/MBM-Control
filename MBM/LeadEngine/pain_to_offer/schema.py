"""schema -- canonical dataclasses for the Pain-to-Offer pipeline.

Mirrors MBM/LeadEngine/property_intel/schema.py conventions.
Every external fact carries provenance (source, source_url, retrieved_at,
verification_status, confidence). Empty means unknown and unknown stays
unknown. Nothing in this module is ever fabricated by code.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import Enum


def _iso_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class EvidenceStatus(str, Enum):
    """Allowed ledger statuses for every factual claim.

    JARVIS contract: only PROVEN and LEADING_HYPOTHESIS may support a pain
    hypothesis; UNVERIFIED claims must NEVER enter outbound copy.
    """

    PROVEN = "PROVEN"
    LEADING_HYPOTHESIS = "LEADING_HYPOTHESIS"
    UNVERIFIED = "UNVERIFIED"
    REJECTED = "REJECTED"


class PipelineState(str, Enum):
    """Explicit pipeline states (mission contract, 16 states)."""

    DISCOVERED = "DISCOVERED"
    RESEARCHING = "RESEARCHING"
    RESEARCHED = "RESEARCHED"
    SCORED = "SCORED"
    OFFER_READY = "OFFER_READY"
    EMAIL_READY = "EMAIL_READY"
    PHONE_PENDING = "PHONE_PENDING"
    CALL_READY = "CALL_READY"
    CONTACTED = "CONTACTED"
    RESPONDED = "RESPONDED"
    MEETING_BOOKED = "MEETING_BOOKED"
    PILOT = "PILOT"
    WON = "WON"
    LOST = "LOST"
    SUPPRESSED = "SUPPRESSED"
    INVALID = "INVALID"


class ContactClass(str, Enum):
    """Contact provenance class. Only BUSINESS_PRACTICE and
    PROFESSIONAL_PUBLIC may enter the outreach pipeline."""

    BUSINESS_PRACTICE = "BUSINESS_PRACTICE"
    PROFESSIONAL_PUBLIC = "PROFESSIONAL_PUBLIC"
    PERSONAL_PRIVATE = "PERSONAL_PRIVATE"


@dataclass
class SourceRef:
    """Provenance for one assertion. source/source_url required."""

    source: str = ""
    source_url: str = ""
    retrieved_at: str = field(default_factory=_iso_now)
    verification_status: str = ""
    confidence: float = 0.0
    evidence_payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Claim:
    """One factual claim with its evidence ledger row.

    Ledger output is exactly CLAIM / STATUS / SOURCE / TIMESTAMP / GAP.
    """

    claim: str
    status: EvidenceStatus = EvidenceStatus.UNVERIFIED
    source: str = ""
    source_url: str = ""
    retrieved_at: str = field(default_factory=_iso_now)
    excerpt: str = ""
    confidence: float = 0.0
    gap: str = ""

    @property
    def supported(self) -> bool:
        return self.status in (EvidenceStatus.PROVEN, EvidenceStatus.LEADING_HYPOTHESIS)

    def ledger_row(self) -> dict:
        return {
            "CLAIM": self.claim,
            "STATUS": self.status.value,
            "SOURCE": self.source,
            "TIMESTAMP": self.retrieved_at,
            "GAP": self.gap,
        }

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class ContactRecord:
    """A contact bound to exactly one company_id.

    contact_class separates business / professional / personal contacts;
    PERSONAL_PRIVATE records are structurally barred from outreach gates.
    """

    contact_id: str = ""
    company_id: str = ""
    name: str = ""
    role: str = ""
    contact_class: ContactClass = ContactClass.BUSINESS_PRACTICE

    email: str = ""
    email_source: str = ""
    email_source_url: str = ""
    email_verification_status: str = ""
    email_verified_at: str = ""

    phone_e164: str = ""
    phone_source: str = ""
    phone_source_url: str = ""
    phone_verification_status: str = ""
    phone_verified_at: str = ""
    phone_confidence: float = 0.0

    campaign_eligible: bool = False

    dedupe_key: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["contact_class"] = self.contact_class.value
        return d


@dataclass
class CompanyEvidencePack:
    """The OX ALPHA 2 per-company evidence pack (the binding contract).

    Targeting fields prove identity/reachability ONLY.
    Pain fields carry the separate pain hypothesis + supporting claims.
    The two groups are never merged.
    """

    company_id: str = ""
    practice_name: str = ""
    practice_type: str = ""
    address: str = ""
    city: str = ""
    state: str = ""
    website: str = ""

    npi_identifier: str = ""
    npi_source: SourceRef = field(default_factory=SourceRef)
    npi_retrieval_timestamp: str = ""

    business_phone: str = ""
    phone_source: SourceRef = field(default_factory=SourceRef)
    phone_retrieval_timestamp: str = ""

    owner_or_decision_maker: str = ""
    decision_maker_role: str = ""
    decision_maker_source: SourceRef = field(default_factory=SourceRef)

    practice_location_count: int = 0

    targeting_evidence: list[Claim] = field(default_factory=list)
    pain_hypothesis: EvidenceStatus = EvidenceStatus.UNVERIFIED
    pain_evidence: list[Claim] = field(default_factory=list)
    pain_confidence: float = 0.0

    state: PipelineState = PipelineState.DISCOVERED
    dedupe_key: str = ""
    raw: dict = field(default_factory=dict)

    def identity_verified(self) -> bool:
        return bool(
            self.company_id
            and self.practice_name
            and self.npi_identifier
            and self.npi_source.source
            and self.npi_retrieval_timestamp
        )

    def phone_verified(self) -> bool:
        from pain_to_offer.validation import is_valid_us_phone

        return bool(
            self.business_phone
            and is_valid_us_phone(self.business_phone)
            and self.phone_source.source
            and self.phone_source.verification_status.upper() == "VERIFIED"
            and self.phone_retrieval_timestamp
        )

    def has_supported_pain(self) -> bool:
        return self.pain_hypothesis in (
            EvidenceStatus.PROVEN,
            EvidenceStatus.LEADING_HYPOTHESIS,
        ) and any(c.supported for c in self.pain_evidence)

    def evidence_sources(self) -> list[str]:
        sources: list[str] = []
        for ref in (self.npi_source, self.phone_source, self.decision_maker_source):
            if ref.source:
                sources.append(ref.source)
        for c in (*self.targeting_evidence, *self.pain_evidence):
            if c.source:
                sources.append(c.source)
        return sorted(set(sources))

    def to_ox2_contract(self) -> dict:
        """Emit the exact OX2 key vocabulary mandated by JARVIS."""
        return {
            "company_id": self.company_id,
            "practice_name": self.practice_name,
            "practice_type": self.practice_type,
            "address": self.address,
            "city": self.city,
            "state": self.state,
            "website": self.website,
            "NPI_identifier": self.npi_identifier,
            "NPI_source": self.npi_source.to_dict(),
            "NPI_retrieval_timestamp": self.npi_retrieval_timestamp,
            "business_phone": self.business_phone,
            "phone_source": self.phone_source.to_dict(),
            "phone_retrieval_timestamp": self.phone_retrieval_timestamp,
            "owner_or_decision_maker": self.owner_or_decision_maker,
            "decision_maker_role": self.decision_maker_role,
            "decision_maker_source": self.decision_maker_source.to_dict(),
            "practice_location_count": self.practice_location_count,
            "evidence_pack": [c.to_dict() for c in self.targeting_evidence],
            "pain_hypothesis": self.pain_hypothesis.value,
            "pain_evidence": [c.to_dict() for c in self.pain_evidence],
            "pain_confidence": self.pain_confidence,
            "evidence_sources": self.evidence_sources(),
            "pipeline_state": self.state.value,
            "dedupe_key": self.dedupe_key,
        }


@dataclass
class GateResult:
    """Uniform result object for every gate. Fails closed with reasons."""

    gate: str
    passed: bool
    reasons: list[str] = field(default_factory=list)

    def __bool__(self) -> bool:
        return self.passed


@dataclass
class OfferBinding:
    """Result of binding a canonical offer template to one company."""

    offer_id: str
    company_id: str
    bound: bool
    reasons: list[str] = field(default_factory=list)
    personalization_allowed: bool = False
    hedge_required: bool = True
    bound_at: str = field(default_factory=_iso_now)
