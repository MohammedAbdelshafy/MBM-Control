"""
MBM LeadEngine — Unified Canonical Lead Data Contract & AI Provenance
Defines strict, zero-hallucination schemas shared across dbt, LeadEngine, Groq, and NVIDIA.
"""

from __future__ import annotations
import json
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field, asdict


@dataclass
class AIProvenance:
    """Immutable provenance record for any AI-derived classification or enrichment."""
    field_name: str
    source: str
    model: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    confidence: float = 0.0
    reasoning_signals: List[str] = field(default_factory=list)
    validation_result: str = "VALIDATED"  # VALIDATED | UNVERIFIED | FLAGGED | REJECTED

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CanonicalProperty:
    """Deterministic physical property entity."""
    property_id: str
    site_address: str
    site_city: str
    site_state: str
    site_zip: str
    county: str
    apn: Optional[str] = None
    property_type: str = "UNKNOWN"
    zoning: Optional[str] = None
    building_sqft: Optional[float] = None
    lot_size_acres: Optional[float] = None
    year_built: Optional[int] = None
    assessed_value: Optional[float] = None
    estimated_equity: Optional[float] = None
    tax_delinquent: bool = False
    foreclosure_auction_date: Optional[str] = None
    is_vacant: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CanonicalOwner:
    """Deterministic legal property owner entity."""
    owner_id: str
    owner_name: str
    owner_type: str = "UNKNOWN"  # INDIVIDUAL | CORPORATE | TRUST | UNKNOWN
    mailing_address: Optional[str] = None
    is_absentee: bool = False
    ownership_verified: bool = False
    verification_source: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CanonicalPhone:
    """Deterministic phone contact entity."""
    phone_raw: str
    phone_e164: str
    carrier_type: str = "UNKNOWN"  # WIRELESS | LANDLINE | VOIP | UNKNOWN
    is_callable: bool = False
    is_dnc: bool = False
    verification_status: str = "UNVERIFIED"  # VERIFIED | PROBABLE | UNVERIFIED | BAD_NUMBER

    @staticmethod
    def normalize_phone(raw: str) -> Optional[str]:
        """Normalizes US phone number to E.164 (+1XXXXXXXXXX)."""
        if not raw:
            return None
        digits = re.sub(r"\D", "", str(raw))
        if len(digits) == 10:
            return f"+1{digits}"
        elif len(digits) == 11 and digits.startswith("1"):
            return f"+{digits}"
        return None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CanonicalLead:
    """Unified lead entity spanning dbt marts, AI orchestrator, and dialer gates."""
    lead_id: str
    property: CanonicalProperty
    owner: CanonicalOwner
    phones: List[CanonicalPhone] = field(default_factory=list)
    signals: List[str] = field(default_factory=list)
    seller_intent: str = "UNKNOWN"  # HIGH | MEDIUM | LOW | UNKNOWN
    seller_intent_provenance: Optional[AIProvenance] = None
    deal_score: float = 0.0  # 0.0 - 100.0
    priority_score: float = 0.0  # 0.0 - 100.0
    why_call_now: str = ""
    recommended_opening: str = ""
    recommended_angle: str = ""
    dialer_gate_passed: bool = False
    dialer_rejection_reason: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def validate_deterministic_gate(self) -> bool:
        """Enforces hard deterministic business invariants before dialer dispatch."""
        # 1. Must have at least one valid, callable, non-DNC phone
        callable_phones = [p for p in self.phones if p.is_callable and not p.is_dnc and p.phone_e164]
        if not callable_phones:
            self.dialer_gate_passed = False
            self.dialer_rejection_reason = "NO_CALLABLE_PHONE"
            return False

        # 2. Must have verified owner or established licensed business
        if not self.owner.owner_name or self.owner.owner_name.strip().upper() in ["UNKNOWN", "N/A", "NONE", "CURRENT RESIDENT"]:
            self.dialer_gate_passed = False
            self.dialer_rejection_reason = "UNVERIFIED_OWNER"
            return False

        # 3. Must have valid site address
        if not self.property.site_address or len(self.property.site_address.strip()) < 5:
            self.dialer_gate_passed = False
            self.dialer_rejection_reason = "INVALID_SITE_ADDRESS"
            return False

        self.dialer_gate_passed = True
        self.dialer_rejection_reason = None
        return True

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.seller_intent_provenance:
            d["seller_intent_provenance"] = self.seller_intent_provenance.to_dict()
        return d
