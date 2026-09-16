"""Opportunity Radar data model. JSON-friendly dataclasses only (no new DB).

Persistence reuses the repository's established artifact-store pattern:
atomic JSON files under artifacts/ (same philosophy as clipping_factory
ledger / MBM-Social ledgers). No schema server is introduced.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ClaimType(str, Enum):
    CLAIMED = "CLAIMED"      # asserted by a creator; no evidence
    INFERRED = "INFERRED"    # deduced by Contec from signals
    VERIFIED = "VERIFIED"    # backed by checkable evidence (invoice, API, doc)


class Decision(str, Enum):
    BUILD_NOW = "BUILD_NOW"        # still requires approval if spend > limit
    EXPERIMENT = "EXPERIMENT"
    WATCH = "WATCH"
    ARCHIVE = "ARCHIVE"
    KILL = "KILL"


class Velocity(str, Enum):
    ACCELERATING = "accelerating"
    STABLE = "stable"
    DECLINING = "declining"
    EMERGING = "emerging"
    SATURATED = "saturated"


@dataclass
class Signal:
    """One raw observation from a source adapter or the operator."""
    signal_id: str
    source: str                    # adapter name: reddit_rss, github_search, operator...
    url: str = ""
    title: str = ""
    body: str = ""
    observed_at: str = field(default_factory=now_iso)
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PlatformChange:
    """A meaningful platform/AI-ecosystem change with business translation."""
    change_id: str
    platform: str                  # instagram, meta_ai, openai, google_ai, anthropic...
    feature: str
    previous_capability: str
    new_capability: str
    who_benefits: str
    business_implication: str
    contec_opportunity: str
    affected_systems: List[str] = field(default_factory=list)
    required_implementation: str = ""
    source_url: str = ""
    observed_at: str = field(default_factory=now_iso)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OpportunityCard:
    """Output of ANALYZE_OPPORTUNITY_CONTENT (Reel/transcript/URL/description).
    Revenue claims are NEVER stored as fact: every claim carries ClaimType."""
    card_id: str
    title: str
    business_model: str = ""
    product_service: str = ""
    target_customer: str = ""
    acquisition_method: str = ""
    fulfillment_method: str = ""
    tools_used: List[str] = field(default_factory=list)
    claimed_price_usd: Optional[float] = None
    recurring_revenue: bool = False
    automation_potential: int = 50          # 0-100
    demand_signal: str = ""
    operational_complexity: int = 50        # 0-100
    risks: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    evidence: List[Dict[str, Any]] = field(default_factory=list)  # {claim,type,evidence}
    source_signals: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Opportunity:
    """A clustered opportunity (many signals -> ONE opportunity)."""
    opportunity_id: str
    cluster_name: str                       # e.g. REAL_ESTATE_AI_MEDIA
    title: str
    cards: List[OpportunityCard] = field(default_factory=list)
    signal_count: int = 0
    sources_seen: List[str] = field(default_factory=list)
    first_seen: str = field(default_factory=now_iso)
    last_seen: str = field(default_factory=now_iso)
    score: float = 0.0
    decision: str = Decision.WATCH.value
    velocity: str = Velocity.EMERGING.value
    reuse_scores: Dict[str, str] = field(default_factory=dict)   # capability -> HIGH/MEDIUM/LOW/NONE
    missing_capabilities: List[str] = field(default_factory=list)
    estimated_monthly_revenue_usd: Optional[float] = None
    time_to_first_revenue_days: Optional[int] = None
    build_effort_days: Optional[int] = None
    human_approval_required: bool = True
    history: List[Dict[str, Any]] = field(default_factory=list)

    def add_evidence(self, card: OpportunityCard, source: str) -> None:
        self.cards.append(card)
        self.signal_count += len(card.source_signals) or 1
        if source not in self.sources_seen:
            self.sources_seen.append(source)
        self.last_seen = now_iso()

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d


@dataclass
class Experiment:
    """OPPORTUNITY_EXPERIMENT: validate demand before building infrastructure.
    Philosophy: SELL -> VALIDATE -> AUTOMATE -> SCALE."""
    experiment_id: str
    opportunity_id: str
    hypothesis: str
    target_customer: str
    offer: str
    acquisition_channel: str
    required_assets: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    budget_limit_usd: float = 0.0
    time_limit_days: int = 14
    success_criteria: Dict[str, Any] = field(default_factory=dict)   # e.g. {"conversations": 5}
    failure_criteria: Dict[str, Any] = field(default_factory=dict)
    owner: str = "operator"
    status: str = "proposed"            # proposed|approved|running|scaled|killed|completed
    approved_by: str = ""
    start_date: str = ""
    end_date: str = ""
    revenue_usd: float = 0.0
    costs_usd: float = 0.0
    leads: int = 0
    conversations: int = 0
    customers: int = 0
    gross_margin_usd: float = 0.0

    @property
    def conversion_rate(self) -> float:
        return round(self.customers / self.conversations, 4) if self.conversations else 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["conversion_rate"] = self.conversion_rate
        return d
