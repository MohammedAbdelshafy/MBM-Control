"""
MBM LeadEngine — Deal Submission Engine
========================================
Low-friction deal intake portal for deal sources (wholesalers, agents, investors).
Validates, underwrites, scores, and routes deals to buyer matching.
"""

from __future__ import annotations
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parents[2]


class DealStatus(str, Enum):
    INTAKE = "INTAKE"
    VALIDATING = "VALIDATING"
    UNDERWRITING = "UNDERWRITING"
    SCORED = "SCORED"
    MATCHING = "MATCHING"
    BUYER_FOUND = "BUYER_FOUND"
    OUTREACH_SENT = "OUTREACH_SENT"
    UNDER_CONTRACT = "UNDER_CONTRACT"
    ASSIGNED = "ASSIGNED"
    CLOSED = "CLOSED"
    LOST = "LOST"
    REJECTED = "REJECTED"


class ContractStatus(str, Enum):
    UNDER_CONTRACT = "UNDER_CONTRACT"
    OPTION_PERIOD = "OPTION_PERIOD"
    PENDING = "PENDING"
    NO_CONTRACT = "NO_CONTRACT"
    assignable = "ASSIGNABLE"


class OccupancyStatus(str, Enum):
    VACANT = "VACANT"
    OWNER_OCCUPIED = "OWNER_OCCUPIED"
    TENANT_OCCUPIED = "TENANT_OCCUPIED"
    UNKNOWN = "UNKNOWN"


@dataclass
class DealSubmission:
    """A deal submitted by a deal source."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])

    # Contact (Deal Source)
    source_name: str = ""
    source_phone: str = ""
    source_email: str = ""
    source_platform: str = ""   # instagram, facebook, referral, manual
    source_username: str = ""
    jv_split: str = "50/50"

    # Property
    address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    county: str = ""
    property_type: str = "SFR"

    # Deal
    contract_status: str = "NO_CONTRACT"
    asking_price: float = 0.0
    contract_price: float = 0.0
    arv: float = 0.0
    arv_source: str = ""
    estimated_repairs: float = 0.0
    repair_source: str = ""
    occupancy: str = "UNKNOWN"
    beds: int = 0
    baths: float = 0.0
    sqft: int = 0
    lot_acres: float = 0.0
    year_built: int = 0

    # Timeline
    closing_date: str = ""
    motivated_reason: str = ""   # divorce, foreclosure, inherited, fire, etc.

    # Media
    photos: List[str] = field(default_factory=list)
    listing_url: str = ""

    # Assignment/JV
    assignment_fee: float = 0.0
    seller_constraints: str = ""

    # Source attribution
    campaign_id: str = ""
    content_id: str = ""
    post_id: str = ""

    # Status
    status: str = "INTAKE"
    deal_score_id: str = ""
    buyer_matches: List[str] = field(default_factory=list)

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationResult:
    """Result of deal data validation."""
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    missing_critical: List[str] = field(default_factory=list)
    missing_optional: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DealSubmissionEngine:
    """Engine for processing deal submissions from deal sources."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or (ROOT_DIR / "MBM" / "LeadEngine" / "deal_submissions.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.deals: Dict[str, DealSubmission] = {}
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                for item in data:
                    deal = DealSubmission(**item)
                    self.deals[deal.id] = deal
            except Exception as e:
                print(f"[WARN] Error loading deal submissions: {e}")

    def save(self) -> None:
        data = [d.to_dict() for d in self.deals.values()]
        self.storage_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def submit_deal(self, deal: DealSubmission) -> DealSubmission:
        """Submit a new deal for processing."""
        deal.status = "INTAKE"
        deal.created_at = datetime.now(timezone.utc).isoformat()
        deal.updated_at = datetime.now(timezone.utc).isoformat()
        self.deals[deal.id] = deal
        self.save()
        return deal

    def validate_deal(self, deal: DealSubmission) -> ValidationResult:
        """Validate deal data completeness and quality."""
        result = ValidationResult()

        # Critical fields (must have for scoring)
        critical = {
            "address": "Property address",
            "city": "City",
            "state": "State",
            "asking_price": "Asking price",
            "property_type": "Property type",
        }
        for field_key, label in critical.items():
            val = getattr(deal, field_key, None)
            if not val or (isinstance(val, (int, float)) and val <= 0 and field_key in ("asking_price",)):
                result.missing_critical.append(label)
                result.is_valid = False

        # Important fields (needed for accurate scoring)
        important = {
            "arv": "After Repair Value (ARV)",
            "estimated_repairs": "Repair estimate",
            "zip_code": "Zip code",
            "contract_status": "Contract status",
            "occupancy": "Occupancy status",
        }
        for field_key, label in important.items():
            val = getattr(deal, field_key, None)
            if not val or (isinstance(val, (int, float)) and val <= 0 and field_key in ("arv", "estimated_repairs")):
                result.missing_optional.append(label)

        # Warnings
        if deal.asking_price > 0 and deal.arv > 0:
            if deal.asking_price > deal.arv:
                result.warnings.append(f"Asking price (${deal.asking_price:,.0f}) exceeds ARV (${deal.arv:,.0f})")
        if deal.estimated_repairs > 0 and deal.arv > 0:
            if deal.estimated_repairs > deal.arv * 0.5:
                result.warnings.append(f"Repair estimate ({deal.estimated_repairs/deal.arv*100:.0f}% of ARV) is high")

        return result

    def transition_status(self, deal_id: str, new_status: str, reason: str = "") -> Optional[DealSubmission]:
        """Transition deal to a new status."""
        deal = self.deals.get(deal_id)
        if not deal:
            return None

        deal.status = new_status
        deal.updated_at = datetime.now(timezone.utc).isoformat()
        self.save()
        return deal

    def get_deals_by_status(self, status: str) -> List[DealSubmission]:
        """Get all deals in a specific status."""
        return [d for d in self.deals.values() if d.status == status]

    def get_active_deals(self) -> List[DealSubmission]:
        """Get all deals not in terminal state."""
        terminal = {"CLOSED", "LOST", "REJECTED"}
        return [d for d in self.deals.values() if d.status not in terminal]

    def get_deals_for_disposition(self) -> List[DealSubmission]:
        """Get deals ready for buyer matching and disposition."""
        ready_statuses = {"SCORED", "MATCHING", "BUYER_FOUND", "OUTREACH_SENT"}
        return [d for d in self.deals.values() if d.status in ready_statuses]

    def to_deal_dict(self, deal: DealSubmission) -> Dict[str, Any]:
        """Convert DealSubmission to dict format expected by DealScoringEngine."""
        return {
            "id": deal.id,
            "address": deal.address,
            "city": deal.city,
            "state": deal.state,
            "zip_code": deal.zip_code,
            "county": deal.county,
            "property_type": deal.property_type,
            "asking_price": deal.asking_price,
            "contract_price": deal.contract_price,
            "arv": deal.arv,
            "arv_source": deal.arv_source,
            "estimated_repairs": deal.estimated_repairs,
            "repair_source": deal.repair_source,
            "occupancy": deal.occupancy,
            "beds": deal.beds,
            "baths": deal.baths,
            "sqft": deal.sqft,
            "lot_acres": deal.lot_acres,
            "year_built": deal.year_built,
            "closing_date": deal.closing_date,
            "contract_status": deal.contract_status,
            "source": deal.source_platform,
            "source_name": deal.source_name,
        }
