"""pain_to_offer -- shared contract package for the Pain-to-Offer pipeline.

Single source of truth for schemas, gates, states, and scoring.
OX ALPHA 2 (research), OX ALPHA 3 (qualification/queues), and Antigravity
(email execution) MUST import from here. Terminals may not invent
competing schemas.

Core invariants:
  - Targeting evidence (a practice exists, has a phone) is NOT pain evidence.
  - UNVERIFIED and REJECTED claims never enter outbound copy.
  - No verified business phone -> no CALL_READY. Ever.
  - No supported pain evidence + personalization basis -> no EMAIL_READY.
  - Personal contacts never enter the outreach pipeline.
"""
from pain_to_offer.gates import (
    SuppressionList,
    call_gate,
    copy_safety,
    email_gate,
    offer_binding_gate,
    pain_gate,
    suppression_check,
)
from pain_to_offer.schema import (
    Claim,
    CompanyEvidencePack,
    ContactClass,
    ContactRecord,
    EvidenceStatus,
    GateResult,
    OfferBinding,
    PipelineState,
    SourceRef,
)
from pain_to_offer.scoring import pain_score, rank_packs
from pain_to_offer.state_machine import ALLOWED_TRANSITIONS, validate_transition
from pain_to_offer.validation import (
    contact_dedupe_key,
    is_plausible_email,
    is_valid_us_phone,
    normalize_phone,
    practice_dedupe_key,
)

__all__ = [
    "ALLOWED_TRANSITIONS",
    "Claim",
    "CompanyEvidencePack",
    "ContactClass",
    "ContactRecord",
    "EvidenceStatus",
    "GateResult",
    "OfferBinding",
    "PipelineState",
    "SourceRef",
    "SuppressionList",
    "call_gate",
    "contact_dedupe_key",
    "copy_safety",
    "email_gate",
    "is_plausible_email",
    "is_valid_us_phone",
    "normalize_phone",
    "offer_binding_gate",
    "pain_gate",
    "pain_score",
    "practice_dedupe_key",
    "rank_packs",
    "suppression_check",
    "validate_transition",
]

__version__ = "1.0.0"
