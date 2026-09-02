"""
Normalized internal contracts — provider-agnostic.

Nothing in LeadEngine should depend on a provider's raw payload shape.
Every adapter normalizes to these types + preserves provenance.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import hashlib
import json


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class Provenance:
    provider: str
    provider_object_id: Optional[str] = None
    source_url: Optional[str] = None
    source_type: Optional[str] = None
    captured_at: str = field(default_factory=_now_iso)
    raw_metadata_hash: Optional[str] = None
    content_hash: Optional[str] = None
    transformation_lineage: List[str] = field(default_factory=list)
    confidence: Optional[float] = None
    # legacy compat for tests/adapters
    tool: Optional[str] = None
    rawReference: Optional[str] = None


from enum import Enum

class OpportunityStatus(Enum):
    DISCOVERED = "DISCOVERED"
    NORMALIZED = "NORMALIZED"
    SCORED = "SCORED"
    REVIEW_REQUIRED = "REVIEW_REQUIRED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CONSUMED = "CONSUMED"


@dataclass
class IntelligenceEvent:
    id: str
    source: str
    category: str
    title: str
    sourceUrl: Optional[str] = None
    observedAt: str = field(default_factory=_now_iso)
    publishedAt: Optional[str] = None
    summary: Optional[str] = None
    entities: List[str] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    topics: List[str] = field(default_factory=list)
    confidence: Optional[float] = None
    freshnessSeconds: Optional[int] = None
    rawReference: Optional[str] = None
    provenance: Provenance = field(default_factory=lambda: Provenance(provider="unknown"))

    def stable_id(self) -> str:
        h = hashlib.sha256(f"{self.source}|{self.title}|{self.publishedAt or self.observedAt}".encode()).hexdigest()[:16]
        return self.id or f"evt_{h}"


@dataclass
class AffiliateOffer:
    offerId: str
    merchantId: Optional[str] = None
    merchantName: Optional[str] = None
    vertical: Optional[str] = None
    commissionRate: Optional[float] = None
    commissionType: Optional[str] = None
    recurring: Optional[bool] = None
    payoutTerms: Optional[str] = None
    cookieWindowDays: Optional[int] = None
    allowedChannels: List[str] = field(default_factory=list)
    restrictions: List[str] = field(default_factory=list)
    sourceUrl: Optional[str] = None
    verifiedAt: str = field(default_factory=_now_iso)
    confidence: float = 0.0  # 0..1 ; 0 = NOT_VERIFIED
    status: str = "VERIFIED"  # VERIFIED | NOT_VERIFIED | BLOCKED

    def to_dict(self) -> Dict[str, Any]:
        return {
            "offerId": self.offerId,
            "merchantId": self.merchantId,
            "merchantName": self.merchantName,
            "vertical": self.vertical,
            "commissionRate": self.commissionRate,
            "commissionType": self.commissionType,
            "recurring": self.recurring,
            "payoutTerms": self.payoutTerms,
            "cookieWindowDays": self.cookieWindowDays,
            "allowedChannels": self.allowedChannels,
            "restrictions": self.restrictions,
            "sourceUrl": self.sourceUrl,
            "verifiedAt": self.verifiedAt,
            "confidence": self.confidence,
            "status": self.status,
        }


@dataclass
class Opportunity:
    opportunity_id: str
    source_event_id: str
    source_provider: str
    source_url: Optional[str] = None
    detected_at: str = field(default_factory=_now_iso)
    title: str = ""
    summary: str = ""
    niche: str = ""
    audience: str = ""
    signal_score: float = 0.0
    freshness_score: float = 0.0
    monetization_score: float = 0.0
    feasibility_score: float = 0.0
    risk_score: float = 0.0
    total_score: float = 0.0
    confidence: float = 0.0
    provenance: Provenance = field(default_factory=lambda: Provenance(provider="unknown"))
    recommended_action: str = ""
    status: OpportunityStatus = OpportunityStatus.DISCOVERED
    created_at: str = field(default_factory=_now_iso)
    updated_at: str = field(default_factory=_now_iso)

    def is_provenance_complete(self) -> bool:
        p = self.provenance
        if not p.provider or not p.provider_object_id or not p.source_url or not p.source_type:
            return False
        if not p.captured_at or not p.raw_metadata_hash or not p.content_hash:
            return False
        if not p.transformation_lineage or p.confidence is None:
            return False
        return True


@dataclass
class CreativeVariant:
    variantId: str
    experimentId: str
    sourceAssetId: str
    platform: str
    config: Dict[str, Any] = field(default_factory=dict)
    prompt: Optional[str] = None
    assetUrl: Optional[str] = None
    createdAt: str = field(default_factory=_now_iso)
    status: str = "generated"  # generated | published | measured
    metrics: Dict[str, Any] = field(default_factory=dict)


def compute_idempotency_key(provider: str, payload: Dict[str, Any]) -> str:
    raw = json.dumps({"provider": provider, "payload": payload}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


# Legacy alias — pre-airlock code used ContentOpportunity; new code uses Opportunity.
# Keep alias so both import paths work and existing tests stay green.
ContentOpportunity = Opportunity

# Back-compat shims for Provenance fields that older adapters expect:
# Older code used `retrievedAt`, `tool`, `rawReference`, `transform`.
# Map them to new fields if accessed.
def _provenance_getattr(self, name):
    if name == "retrievedAt":
        return getattr(self, "captured_at", None)
    if name == "transform":
        lineage = getattr(self, "transformation_lineage", [])
        return lineage[0] if lineage else None
    raise AttributeError(name)

# Monkey-patch for legacy attribute access (only if not already present)
if not hasattr(Provenance, "retrievedAt"):
    Provenance.retrievedAt = property(lambda self: self.captured_at)
if not hasattr(Provenance, "transform"):
    Provenance.transform = property(lambda self: (self.transformation_lineage[0] if self.transformation_lineage else None))
if not hasattr(Provenance, "rawReference"):
    Provenance.rawReference = property(lambda self: self.raw_metadata_hash)
if not hasattr(Provenance, "sourceUrl"):
    Provenance.sourceUrl = property(lambda self: self.source_url)
