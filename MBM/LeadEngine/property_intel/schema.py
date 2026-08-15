"""schema -- canonical dataclasses for the property intelligence pipeline.

Each external fact carries provenance (source, source_url, source_date,
retrieved_at, verification_status, confidence). No field is ever fabricated;
empty means unknown and unknown stays unknown.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

ENTITY_MARKERS = (
    "LLC", "LP", "INC", "CORP", "TRUST", "GROUP", "PROPERTIES", "PROPERTY",
    "INVESTMENTS", "REALTY", "HOLDINGS", "LTD", "COMPANY", "PARTNERSHIP",
    "LLP", "PA", "HOMES", "ESTATE", "HOLDING", "ENTERPRISES", "L.C.",
    "L.L.C.", "PLLC", "PC", "ASSOCIATION", "CHURCH", "FOUNDATION",
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class SourceRef:
    """Provenance for one assertion. source/source_url are required."""

    source: str
    source_url: str
    retrieved_at: str = field(default_factory=_iso_now)
    source_date: str = ""
    verification_status: str = ""
    confidence: str = ""          # high | medium | low
    note: str = ""
    evidence_payload: dict = field(default_factory=dict)  # raw matched row

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


@dataclass
class PropertyRecord:
    """A normalized property with provenance. parcel_id = APN when known."""

    property_id: str = ""
    address: str = ""
    address_normalized: str = ""
    city: str = ""
    state: str = ""
    county: str = ""
    zip_code: str = ""
    parcel_id: str = ""
    source: str = ""
    source_url: str = ""
    source_date: str = ""
    retrieved_at: str = field(default_factory=_iso_now)
    auction_date: str = ""
    auction_status: str = ""      # foreclosure | pre-foreclosure | tax_deed | bankruptcy | reo | unknown
    opening_bid: Optional[float] = None
    estimated_value: Optional[float] = None
    occupancy_signal: str = ""    # vacant | occupied | unknown
    distress_signals: list[str] = field(default_factory=list)
    dedupe_key: str = ""
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)
        return d


@dataclass
class AuctionRecord:
    """Raw listing pulled from a source (Auction.com or a pre-collected file)."""

    address: str = ""
    city: str = ""
    state: str = ""
    county: str = ""
    zip_code: str = ""
    parcel_id: str = ""
    auction_date: str = ""
    auction_status: str = ""
    opening_bid: str = ""          # keep raw text until parsed
    estimated_value: str = ""      # keep raw text until parsed
    source: str = ""
    source_url: str = ""
    source_date: str = ""
    occupancy_signal: str = ""
    notes: str = ""
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class OwnershipVerification:
    """Result of verifying legal owner from an authoritative/authorized source."""

    property_key: str = ""
    owner_name: str = ""
    owner_type: str = "unknown"    # individual | entity | trust | unknown
    parcel_id: str = ""
    site_address: str = ""
    mailing_address: str = ""
    source: str = ""
    source_url: str = ""
    retrieved_at: str = field(default_factory=_iso_now)
    verification_status: str = "NOT_FOUND"   # VERIFIED | LIKELY | NOT_FOUND | CONFLICT
    confidence: float = 0.0
    evidence: list[SourceRef] = field(default_factory=list)
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["evidence"] = [e.to_dict() for e in self.evidence]
        return d


@dataclass
class ScoreResult:
    """Structured score with component values and reason trace (issue #23)."""

    total: int = 0
    component_scores: dict = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)  # [{component,score,weight,reason}]

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BusinessProspect:
    """Business-owner AI-services prospect. Contact fields only from authorized
    sources; never fabricated."""

    prospect_id: str = ""
    company_name: str = ""
    category: str = ""
    website: str = ""
    business_phone: str = ""
    owner_name: str = ""
    email: str = ""
    city: str = ""
    state: str = ""
    rating: Optional[float] = None
    review_count: int = 0
    source: str = ""
    source_url: str = ""
    retrieved_at: str = field(default_factory=_iso_now)
    signals: list[str] = field(default_factory=list)
    scores: dict = field(default_factory=dict)
    fit_score: int = 0
    pay_score: int = 0
    reason_trace: list[dict] = field(default_factory=list)
    verification_status: str = "UNVERIFIED"
    confidence: float = 0.0
    raw: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("raw", None)
        return d


def classify_owner_type(name: str) -> str:
    """Classify an owner name into individual | entity | trust | unknown.

    Uses surface markers only; never invents. A joint person name stays
    'individual'. Unknown when blank.
    """
    if not name or not str(name).strip():
        return "unknown"
    upper = str(name).upper()
    if "TRUST" in upper or "TRUSTEE" in upper or "LIVING TRUST" in upper:
        return "trust"
    if any(m in upper for m in ENTITY_MARKERS):
        return "entity"
    return "individual"


def money_to_float(text: Any) -> Optional[float]:
    """Parse '$225,000' / '225000' -> 225000.0; None when absent/garbage."""
    if text is None:
        return None
    s = str(text).strip().replace(",", "")
    m = re.search(r"-?\d+(?:\.\d+)?", s)
    if not m:
        return None
    return float(m.group(0))