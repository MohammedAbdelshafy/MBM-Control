"""gates -- fail-closed eligibility gates. Every gate returns a GateResult.

Gate law (JARVIS contract):
  - offer binding requires company_id + verified identity + verified business
    phone + supported pain hypothesis.
  - EMAIL_READY additionally requires campaign eligibility, suppression pass,
    legitimate business/professional contact class, and personalization
    evidence (supported pain).
  - CALL_READY requires a valid US business/practice number with verified
    status, verification source, timestamp, company association, and
    confidence >= threshold.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from pain_to_offer.schema import (
    Claim,
    CompanyEvidencePack,
    ContactClass,
    ContactRecord,
    EvidenceStatus,
    GateResult,
    OfferBinding,
)
from pain_to_offer.validation import (
    contact_dedupe_key,
    is_plausible_email,
    is_valid_us_phone,
)

CALL_MIN_CONFIDENCE = 0.8

STRONG_PAIN_MARKERS = (
    "misses calls",
    "missed calls",
    "missing calls",
    "losing patients",
    "overwhelmed",
    "leaking revenue",
    "bleeding revenue",
)

HEDGED_LINE = "Potential missed-call recovery opportunity"


@dataclass
class SuppressionList:
    """Registry of permanently barred phones / emails / companies."""

    entries: set[str] = field(default_factory=set)

    def add(self, value: str) -> None:
        if value:
            self.entries.add(contact_dedupe_key(value))

    def contains(self, value: str) -> bool:
        return contact_dedupe_key(value) in self.entries


def suppression_check(
    suppression: SuppressionList,
    *values: str,
) -> tuple[bool, list[str]]:
    hits = [v for v in values if v and suppression.contains(v)]
    return (not hits), hits


def offer_binding_gate(
    pack: CompanyEvidencePack,
    offer_id: str = "DENTAL-MCR-001",
) -> OfferBinding:
    """Bind a canonical offer template to exactly one company."""

    def reject(*reasons: str) -> OfferBinding:
        return OfferBinding(
            offer_id=offer_id, company_id=pack.company_id,
            bound=False, reasons=list(reasons),
        )

    if not pack.company_id:
        return reject("missing company_id: canonical offer cannot bind")
    if not pack.identity_verified():
        return reject("NPI/business identity not verified with source + timestamp")
    if not pack.phone_verified():
        return reject("business phone not verified with source + timestamp")
    if not pack.pain_evidence:
        return reject("empty evidence pack")
    if not pack.has_supported_pain():
        return reject(
            "pain_hypothesis must be PROVEN or LEADING_HYPOTHESIS "
            f"(got {pack.pain_hypothesis.value})"
        )
    return OfferBinding(
        offer_id=offer_id,
        company_id=pack.company_id,
        bound=True,
        personalization_allowed=True,
        hedge_required=(pack.pain_hypothesis != EvidenceStatus.PROVEN),
    )


def pain_gate(pack: CompanyEvidencePack) -> GateResult:
    """Eligible-for-scoring gate: targeting evidence alone never passes."""
    reasons: list[str] = []
    if not pack.identity_verified():
        reasons.append("identity not verified")
    if not pack.has_supported_pain():
        if pack.pain_evidence:
            reasons.append(
                "pain claims exist but none carry PROVEN/LEADING_HYPOTHESIS status"
            )
        else:
            reasons.append("no pain evidence at all: targeting evidence is not pain evidence")
    return GateResult(gate="pain_eligibility", passed=not reasons, reasons=reasons)


def _personalization_basis(pack: CompanyEvidencePack) -> list[str]:
    if pack.has_supported_pain():
        return []
    return ["no supported pain evidence: cannot personalize outreach"]


def email_gate(
    pack: CompanyEvidencePack,
    contact: ContactRecord,
    suppression: SuppressionList,
) -> GateResult:
    reasons: list[str] = []

    if not contact.contact_id or not contact.company_id:
        reasons.append("contact missing contact_id/company_id")
    elif contact.company_id != pack.company_id:
        reasons.append("contact not associated with this company")

    clean, hits = suppression_check(suppression, contact.email, contact.phone_e164, pack.company_id)
    if not clean:
        reasons.append(f"suppressed: {hits}")

    if contact.contact_class == ContactClass.PERSONAL_PRIVATE:
        reasons.append("PERSONAL_PRIVATE contacts may never enter outreach")

    if not is_plausible_email(contact.email):
        reasons.append("invalid or missing email")
    else:
        if not contact.email_source:
            reasons.append("email has no source")
        if contact.email_verification_status.upper() != "VERIFIED":
            reasons.append("email not verification-status VERIFIED")
        if not contact.email_verified_at:
            reasons.append("email verification timestamp missing")

    if not contact.campaign_eligible:
        reasons.append("campaign_eligible is false")

    reasons.extend(_personalization_basis(pack))

    return GateResult(gate="email_ready", passed=not reasons, reasons=reasons)


def call_gate(
    pack: CompanyEvidencePack,
    contact: ContactRecord,
    suppression: SuppressionList,
) -> GateResult:
    reasons: list[str] = []

    if not contact.company_id:
        reasons.append("contact missing company_id")
    elif contact.company_id != pack.company_id:
        reasons.append("phone not associated with this business record")

    clean, hits = suppression_check(suppression, contact.phone_e164, contact.email, pack.company_id)
    if not clean:
        reasons.append(f"suppressed: {hits}")

    if contact.contact_class == ContactClass.PERSONAL_PRIVATE:
        reasons.append("PERSONAL_PRIVATE numbers may never enter outreach")

    if not is_valid_us_phone(contact.phone_e164):
        reasons.append("not a valid US business/practice number")
    else:
        if contact.phone_verification_status.upper() != "VERIFIED":
            reasons.append("phone verification status is not VERIFIED")
        if not contact.phone_source:
            reasons.append("phone verification source missing")
        if not contact.phone_verified_at:
            reasons.append("phone verification timestamp missing")
        if contact.phone_confidence < CALL_MIN_CONFIDENCE:
            reasons.append(
                f"phone_confidence {contact.phone_confidence} < {CALL_MIN_CONFIDENCE}"
            )

    return GateResult(gate="call_ready", passed=not reasons, reasons=reasons)


def copy_safety(claim: Claim) -> tuple[bool, str, str]:
    """Return (allowed, safe_text, reason) for outbound use of a claim.

    PROVEN             -> verbatim allowed.
    LEADING_HYPOTHESIS -> forced hedge phrasing.
    UNVERIFIED/REJECTED-> blocked from all outbound copy.
    """
    lowered = (claim.claim or "").lower()
    strong = any(m in lowered for m in STRONG_PAIN_MARKERS)

    if claim.status == EvidenceStatus.PROVEN:
        return True, claim.claim, ""
    if claim.status == EvidenceStatus.LEADING_HYPOTHESIS:
        if strong:
            return False, HEDGED_LINE, "strong claim downgraded to mandated hedge"
        return True, claim.claim, ""
    return (
        False,
        "",
        f"claim status {claim.status.value} is banned from outbound copy",
    )


def safe_outreach_claims(claims: Iterable[Claim]) -> list[tuple[Claim, str]]:
    usable: list[tuple[Claim, str]] = []
    for c in claims:
        allowed, text, _ = copy_safety(c)
        if allowed:
            usable.append((c, text))
    return usable
