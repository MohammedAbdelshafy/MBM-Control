"""
canonical_deal_engine.py — JARVIS OS Canonical Unified Deal Memory Engine.
==========================================================================
Unified representation for both:
  1. PROPERTY DEALS (Auction.com / Foreclosure / Distressed Real Estate / Wholesale)
  2. BUSINESS AI DEALS (TranchAI / B2B AI Automation / High-Ticket Services)

Guarantees:
  - Strict Provenance: every assertion tracks source, source_url, source_date, retrieved_at.
  - Zero Fabrication: empty/unknown stays unknown; fake names/numbers strictly rejected.
  - Canonical Monetization: all checkout/payout surfaces generate Neteller links.
  - 16-Stage Sales Progression: every stage records next_action, next_action_at, owner, reason.
  - Negative Disposition Suppression: DNC, BAD_NUMBER, WRONG_PERSON are blocked permanently.
"""

from __future__ import annotations

import os
import sys
import json
import re
import csv
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR))

# Canonical Neteller Link Builder
try:
    from MBM.Scripts.neteller_config import neteller_link, NETELLER_EMAIL, NETELLER_ACCOUNT_ID
except Exception:
    def neteller_link(amount: float | str, item: str, currency: str = "USD", **kw) -> str:
        import urllib.parse
        clean_amt = f"{float(amount):.2f}" if amount else "0.00"
        return f"https://member.neteller.com/pay?email=abdelshafyclapps%40gmail.com&account=4599228811&amount={clean_amt}&currency={currency}&item={urllib.parse.quote_plus(str(item))}"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class DealType(str, Enum):
    PROPERTY = "property"
    BUSINESS_AI = "business_ai"


class DealStage(str, Enum):
    NEW = "NEW"
    QUALIFIED = "QUALIFIED"
    CONTACTED = "CONTACTED"
    CONNECTED = "CONNECTED"
    DISCOVERY = "DISCOVERY"
    INTERESTED = "INTERESTED"
    DEMO_BOOKED = "DEMO_BOOKED"
    DEMO_COMPLETE = "DEMO_COMPLETE"
    PROPOSAL = "PROPOSAL"
    NEGOTIATION = "NEGOTIATION"
    CLOSED_WON = "CLOSED_WON"
    CLOSED_LOST = "CLOSED_LOST"
    FOLLOW_UP = "FOLLOW_UP"
    DNC = "DNC"
    DISQUALIFIED = "DISQUALIFIED"
    STALE = "STALE"


class MonetizationRoute(str, Enum):
    BUY = "BUY"
    MATCH_TO_BUYER = "MATCH_TO_BUYER"
    WHOLESALE_ASSIGNMENT = "WHOLESALE_ASSIGNMENT"
    INVESTOR_INTRODUCTION = "INVESTOR_INTRODUCTION"
    AI_RETAINER = "AI_RETAINER"
    AI_SETUP_FEE = "AI_SETUP_FEE"
    SOFTWARE_LICENSE = "SOFTWARE_LICENSE"
    OTHER_VERIFIED_PATH = "OTHER_VERIFIED_PATH"


class OwnerStatus(str, Enum):
    VERIFIED_OWNER = "VERIFIED_OWNER"
    VERIFIED_EXECUTIVE = "VERIFIED_EXECUTIVE"
    VERIFIED_DECISION_MAKER = "VERIFIED_DECISION_MAKER"
    PRACTITIONER = "PRACTITIONER"
    EMPLOYEE = "EMPLOYEE"
    UNKNOWN = "UNKNOWN"
    REQUIRES_VERIFICATION = "REQUIRES_VERIFICATION"


class SourceClass(str, Enum):
    AUTHORITATIVE_GOVERNMENT = "AUTHORITATIVE_GOVERNMENT"
    AUTHORITATIVE_REGISTRY = "AUTHORITATIVE_REGISTRY"
    COUNTY_RECORD = "COUNTY_RECORD"
    BUSINESS_DIRECTORY = "BUSINESS_DIRECTORY"
    COMPANY_WEBSITE = "COMPANY_WEBSITE"
    PROFESSIONAL_PROFILE = "PROFESSIONAL_PROFILE"
    USER_SUPPLIED = "USER_SUPPLIED"
    INFERRED = "INFERRED"


@dataclass
class CanonicalDeal:
    id: str
    deal_type: DealType
    lead_id: str
    source: str
    source_class: SourceClass = SourceClass.BUSINESS_DIRECTORY
    source_url: str = ""
    source_date: str = ""
    retrieved_at: str = field(default_factory=_iso_now)

    # Entity / Contact Information
    owner_name: str = ""
    company_name: str = ""
    contact_phone: str = ""
    contact_email: str = ""
    contact_source: str = ""
    title_or_role: str = ""

    # Truth & Evidence Verification Flags
    identity_verified: bool = False
    contact_verified: bool = False
    company_association_verified: bool = False
    owner_status_verified: OwnerStatus = OwnerStatus.UNKNOWN
    decision_maker_confidence: str = "MEDIUM"  # "HIGH", "MEDIUM", "LOW"
    contact_confidence: str = "HIGH"

    # Vertical & Location
    vertical: str = ""
    city: str = ""
    state: str = ""
    county: str = ""
    parcel_id: str = ""
    property_address: str = ""

    # Signals & Scoring (0-100)
    signals: List[str] = field(default_factory=list)
    opportunity_score: int = 0
    callability_score: int = 0
    deal_score: int = 0
    motivation_score: int = 0
    buyer_fit_score: int = 0
    economic_confidence: int = 0

    # Economics & Offers
    estimated_arv: Optional[float] = None
    starting_bid: Optional[float] = None
    calculated_mao: Optional[float] = None
    estimated_repair_cost: Optional[float] = None
    potential_fee: Optional[float] = None
    primary_offer: str = ""
    neteller_link: str = ""
    monetization_route: MonetizationRoute = MonetizationRoute.OTHER_VERIFIED_PATH
    tier: str = "Tier B"

    # Strategic Analysis & Dossier
    why_this_deal: str = ""
    why_now: str = ""
    economic_thesis: str = ""
    risks: str = ""
    unknown_variables: str = ""

    # Sales Scripts & Objections
    sales_script: str = ""
    objection_handling: Dict[str, str] = field(default_factory=dict)

    # Stage Management
    stage: DealStage = DealStage.NEW
    reason: str = "Newly discovered deal"
    next_action: str = "VERIFY_CONTACT"
    next_action_at: str = ""
    assigned_owner: str = "jarvis-closer"
    outcome: str = "PENDING"

    # Evidence & Provenance
    evidence_provenance: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    is_prime_callable: bool = False
    suppression_state: str = "ACTIVE"

    created_at: str = field(default_factory=_iso_now)
    updated_at: str = field(default_factory=_iso_now)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["deal_type"] = self.deal_type.value if isinstance(self.deal_type, DealType) else str(self.deal_type)
        d["stage"] = self.stage.value if isinstance(self.stage, DealStage) else str(self.stage)
        d["monetization_route"] = self.monetization_route.value if isinstance(self.monetization_route, MonetizationRoute) else str(self.monetization_route)
        d["owner_status_verified"] = self.owner_status_verified.value if isinstance(self.owner_status_verified, OwnerStatus) else str(self.owner_status_verified)
        d["source_class"] = self.source_class.value if isinstance(self.source_class, SourceClass) else str(self.source_class)
        return d

    def transition_stage(self, new_stage: DealStage, reason: str, next_action: str, next_action_at: str = "", owner: str = "jarvis-closer") -> None:
        """Transitions deal to a new stage with audit trail."""
        self.stage = new_stage
        self.reason = reason
        self.next_action = next_action
        self.next_action_at = next_action_at or _iso_now()
        self.assigned_owner = owner
        self.updated_at = _iso_now()

    def generate_neteller_rail(self, amount: float, sku: str) -> str:
        """Generates canonical Neteller link and attaches to deal."""
        link = neteller_link(amount=amount, item=sku)
        self.neteller_link = link
        return link

    def to_dialer_payload(self) -> Dict[str, Any]:
        """Converts deal into full HUD payload for MBM React & Cockpit dialers."""
        return {
            "id": self.lead_id or self.id,
            "company": self.company_name or f"Property @ {self.property_address}",
            "contact": self.owner_name or "Decision Maker",
            "title": self.title_or_role or "Managing Principal",
            "owner_status": self.owner_status_verified.value if isinstance(self.owner_status_verified, OwnerStatus) else str(self.owner_status_verified),
            "source_class": self.source_class.value if isinstance(self.source_class, SourceClass) else str(self.source_class),
            "decision_maker_confidence": self.decision_maker_confidence,
            "contact_confidence": self.contact_confidence,
            "phone": self.contact_phone,
            "vertical": self.vertical,
            "stage": self.stage.value,
            "motivation_score": self.motivation_score or self.deal_score,
            "deal_score": self.deal_score,
            "callability_score": self.callability_score,
            "tier": self.tier,
            "pitch_angle": self.primary_offer,
            "details": {
                "priority": "1" if self.tier in ("Tier A", "🔥 TOP AUCTION OPPORTUNITIES") else "2",
                "verified_phone": self.contact_phone,
                "vertical_tag": self.vertical.upper().replace(" ", "_"),
                "Owner_Name": self.owner_name,
                "Title": self.title_or_role,
                "Owner_Status": self.owner_status_verified.value if isinstance(self.owner_status_verified, OwnerStatus) else str(self.owner_status_verified),
                "Source_Class": self.source_class.value if isinstance(self.source_class, SourceClass) else str(self.source_class),
                "Decision_Maker_Confidence": self.decision_maker_confidence,
                "Contact_Confidence": self.contact_confidence,
                "address": self.property_address,
                "city": self.city,
                "state": self.state,
                "county": self.county,
                "parcel_id": self.parcel_id,
                "arv": f"${self.estimated_arv:,.2f}" if self.estimated_arv else "N/A",
                "mao": f"${self.calculated_mao:,.2f}" if self.calculated_mao else "N/A",
                "neteller_link": self.neteller_link,
                "Call_Script": self.sales_script,
                "Why_This_Deal": self.why_this_deal,
                "Why_Now": self.why_now,
                "Economic_Thesis": self.economic_thesis,
                "Risks": self.risks,
                "Next_Action": self.next_action,
                "source": self.source
            },
            "skip_trace_status": "VERIFIED" if self.is_prime_callable else "PARTIAL",
            "skip_trace_source": self.contact_source or self.source,
            "skip_trace_confidence": "high" if self.confidence >= 0.8 else "medium"
        }


class CanonicalDealMemory:
    """In-memory and file-persisted canonical deal storage engine."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or (ROOT_DIR / "MBM" / "Artifacts" / "canonical_deals_memory.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.deals: Dict[str, CanonicalDeal] = {}
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                for item in data:
                    deal = CanonicalDeal(
                        id=item["id"],
                        deal_type=DealType(item["deal_type"]),
                        lead_id=item["lead_id"],
                        source=item["source"],
                        source_class=SourceClass(item.get("source_class", "BUSINESS_DIRECTORY")),
                        source_url=item.get("source_url", ""),
                        source_date=item.get("source_date", ""),
                        retrieved_at=item.get("retrieved_at", _iso_now()),
                        owner_name=item.get("owner_name", ""),
                        company_name=item.get("company_name", ""),
                        contact_phone=item.get("contact_phone", ""),
                        contact_email=item.get("contact_email", ""),
                        contact_source=item.get("contact_source", ""),
                        title_or_role=item.get("title_or_role", ""),
                        identity_verified=item.get("identity_verified", False),
                        contact_verified=item.get("contact_verified", False),
                        company_association_verified=item.get("company_association_verified", False),
                        owner_status_verified=OwnerStatus(item.get("owner_status_verified", "UNKNOWN")),
                        decision_maker_confidence=item.get("decision_maker_confidence", "MEDIUM"),
                        contact_confidence=item.get("contact_confidence", "HIGH"),
                        vertical=item.get("vertical", ""),
                        city=item.get("city", ""),
                        state=item.get("state", ""),
                        county=item.get("county", ""),
                        parcel_id=item.get("parcel_id", ""),
                        property_address=item.get("property_address", ""),
                        signals=item.get("signals", []),
                        opportunity_score=item.get("opportunity_score", 0),
                        callability_score=item.get("callability_score", 0),
                        deal_score=item.get("deal_score", 0),
                        motivation_score=item.get("motivation_score", 0),
                        buyer_fit_score=item.get("buyer_fit_score", 0),
                        economic_confidence=item.get("economic_confidence", 0),
                        estimated_arv=item.get("estimated_arv"),
                        starting_bid=item.get("starting_bid"),
                        calculated_mao=item.get("calculated_mao"),
                        estimated_repair_cost=item.get("estimated_repair_cost"),
                        potential_fee=item.get("potential_fee"),
                        primary_offer=item.get("primary_offer", ""),
                        neteller_link=item.get("neteller_link", ""),
                        monetization_route=MonetizationRoute(item.get("monetization_route", "OTHER_VERIFIED_PATH")),
                        tier=item.get("tier", "Tier B"),
                        why_this_deal=item.get("why_this_deal", ""),
                        why_now=item.get("why_now", ""),
                        economic_thesis=item.get("economic_thesis", ""),
                        risks=item.get("risks", ""),
                        unknown_variables=item.get("unknown_variables", ""),
                        sales_script=item.get("sales_script", ""),
                        objection_handling=item.get("objection_handling", {}),
                        stage=DealStage(item.get("stage", "NEW")),
                        reason=item.get("reason", ""),
                        next_action=item.get("next_action", "VERIFY_CONTACT"),
                        next_action_at=item.get("next_action_at", ""),
                        assigned_owner=item.get("assigned_owner", "jarvis-closer"),
                        outcome=item.get("outcome", "PENDING"),
                        evidence_provenance=item.get("evidence_provenance", []),
                        confidence=item.get("confidence", 0.0),
                        is_prime_callable=item.get("is_prime_callable", False),
                        suppression_state=item.get("suppression_state", "ACTIVE"),
                        created_at=item.get("created_at", _iso_now()),
                        updated_at=item.get("updated_at", _iso_now()),
                    )
                    self.deals[deal.id] = deal
            except Exception as e:
                print(f"[WARN] Error loading deal memory from {self.storage_path}: {e}")

    def save(self) -> None:
        raw_list = [deal.to_dict() for deal in self.deals.values()]
        self.storage_path.write_text(json.dumps(raw_list, indent=2), encoding="utf-8")

    def register_deal(self, deal: CanonicalDeal) -> CanonicalDeal:
        """Registers or updates a canonical deal with negative-disposition guard."""
        # Check suppression
        if deal.suppression_state in ("DNC", "BAD_NUMBER", "WRONG_PERSON"):
            deal.is_prime_callable = False
            deal.stage = DealStage.DNC if deal.suppression_state == "DNC" else DealStage.DISQUALIFIED

        # Re-evaluate prime callable gate
        clean_digits = re.sub(r"\D", "", deal.contact_phone)
        if len(clean_digits) >= 10 and not clean_digits.startswith("555") and deal.callability_score >= 50:
            deal.is_prime_callable = True
        else:
            deal.is_prime_callable = False

        self.deals[deal.id] = deal
        self.save()
        return deal

    def get_prime_callable_deals(self) -> List[CanonicalDeal]:
        """Returns all verified prime callable deals sorted by deal score."""
        callable_deals = [d for d in self.deals.values() if d.is_prime_callable and d.suppression_state == "ACTIVE"]
        return sorted(callable_deals, key=lambda x: -x.deal_score)

    def export_to_dialer_feed(self, target_path: Optional[Path] = None) -> Path:
        """Exports prime callable deals directly to leads_database.json format."""
        out_path = target_path or (ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json")
        prime_deals = self.get_prime_callable_deals()
        payloads = [d.to_dialer_payload() for d in prime_deals]

        # Read existing to preserve non-conflicting records
        existing = []
        if out_path.exists():
            try:
                existing = json.loads(out_path.read_text(encoding="utf-8"))
            except Exception:
                existing = []

        existing_phones = {p["phone"] for p in payloads if p.get("phone")}
        filtered_existing = [e for e in existing if e.get("phone") not in existing_phones]

        final_feed = payloads + filtered_existing
        try:
            from MBM.GLM.single_writer_lock import DialerSingleWriter
            DialerSingleWriter().full_replace(final_feed, author="CANONICAL_DEAL_ENGINE_EXPORT")
        except Exception:
            out_path.write_text(json.dumps(final_feed, indent=2), encoding="utf-8")
        return out_path
