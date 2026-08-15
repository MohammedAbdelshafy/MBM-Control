"""property_intel -- MBM Property Intelligence + Ownership Verification + Business Prospecting.

DATA side of jarvis-mbm#23 (Worker 2). Worker 1 owns the core platform/schema;
this package produces the canonical normalized records, ownership evidence and
scoring/reason traces that feed it.

Pipeline:  ingest -> normalize -> dedupe -> county route -> ownership verify ->
           score (opportunity + callability) -> gate -> rank -> artifacts.

Honesty contract (mirrors moneybeast / lead_pack_builder):
  - NEVER invents owners, addresses, phones, auction data or intent.
  - A person/entity is only labelled owner when an authoritative or authorized
    source returned it; everything else stays REQUIRES_VERIFICATION.
  - Every external fact preserves provenance: source, source_url, source_date,
    retrieved_at, verification_status, confidence.
"""

from .schema import (  # noqa: F401
    AuctionRecord,
    BusinessProspect,
    OwnershipVerification,
    PropertyRecord,
    ScoreResult,
    SourceRef,
)