"""
MBM LeadEngine — Social CTA Router
====================================
Routes social media interactions into the correct CRM pipeline
based on intent keywords and context. Platform-agnostic.
"""

from __future__ import annotations
import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parents[2]


class IntentType(str, Enum):
    DEAL_SOURCE = "deal_source"
    SELLER = "seller"
    BUYER = "buyer"
    PARTNER = "partner"
    INVESTOR = "investor"
    UNKNOWN = "unknown"


class PipelineType(str, Enum):
    SELLER = "seller"
    BUYER = "buyer"
    DEAL_SOURCE = "deal_source"
    JV_PARTNER = "jv_partner"


class LeadPriority(str, Enum):
    HOT = "HOT"
    WARM = "WARM"
    NORMAL = "NORMAL"
    LOW = "LOW"


# CTA Keywords → Intent routing
CTA_KEYWORDS: Dict[str, IntentType] = {
    # Deal source signals
    "DEAL": IntentType.DEAL_SOURCE,
    "HAVE A DEAL": IntentType.DEAL_SOURCE,
    "CONTRACT": IntentType.DEAL_SOURCE,
    "WHOLESALE": IntentType.DEAL_SOURCE,
    "ASSIGNMENT": IntentType.DEAL_SOURCE,

    # Seller signals
    "SELL": IntentType.SELLER,
    "SELL MY HOUSE": IntentType.SELLER,
    "SELLING": IntentType.SELLER,
    "MOTIVATED": IntentType.SELLER,
    "FORECLOSURE": IntentType.SELLER,
    "DIVORCE": IntentType.SELLER,
    "INHERITED": IntentType.SELLER,
    "FIRE": IntentType.SELLER,
    "ASSESSED": IntentType.SELLER,
    "TAX DELINQUENT": IntentType.SELLER,
    "VACANT": IntentType.SELLER,
    "PROBATE": IntentType.SELLER,
    "CODE VIOLATION": IntentType.SELLER,

    # Buyer signals
    "BUY": IntentType.BUYER,
    "BUYING": IntentType.BUYER,
    "INVESTOR": IntentType.BUYER,
    "CASH BUYER": IntentType.BUYER,
    "LOOKING FOR": IntentType.BUYER,
    "FUNDING": IntentType.BUYER,
    "FLIP": IntentType.BUYER,
    "BRRRR": IntentType.BUYER,

    # JV signals
    "JV": IntentType.PARTNER,
    "PARTNER": IntentType.PARTNER,
    "JOINT VENTURE": IntentType.PARTNER,
    "COLLAB": IntentType.PARTNER,
    "DISPO": IntentType.PARTNER,

    # Investment signals
    "INVEST": IntentType.INVESTOR,
    "INVESTMENT": IntentType.INVESTOR,
    "ROI": IntentType.INVESTOR,
    "PASSIVE INCOME": IntentType.INVESTOR,
}

# Intent → Pipeline routing
INTENT_TO_PIPELINE: Dict[IntentType, PipelineType] = {
    IntentType.DEAL_SOURCE: PipelineType.DEAL_SOURCE,
    IntentType.SELLER: PipelineType.SELLER,
    IntentType.BUYER: PipelineType.BUYER,
    IntentType.PARTNER: PipelineType.JV_PARTNER,
    IntentType.INVESTOR: PipelineType.BUYER,  # Investors are a buyer type
    IntentType.UNKNOWN: PipelineType.SELLER,  # Default to seller
}

# Platform configurations
PLATFORMS: Dict[str, Dict[str, bool]] = {
    "instagram": {"dm_enabled": True, "comment_enabled": True, "story_enabled": True},
    "facebook": {"dm_enabled": True, "comment_enabled": True, "group_enabled": True},
    "tiktok": {"dm_enabled": True, "comment_enabled": True},
    "youtube": {"comment_enabled": True, "form_enabled": True},
    "whatsapp": {"message_enabled": True},
    "website": {"form_enabled": True, "chat_enabled": True},
    "phone": {"call_enabled": True},
    "email": {"message_enabled": True},
    "community": {"post_enabled": True, "dm_enabled": True},
    "manual": {"entry_enabled": True},
    "referral": {"entry_enabled": True},
}


@dataclass
class SocialInteraction:
    """A social media interaction to be routed."""
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:12])
    platform: str = ""
    username: str = ""
    display_name: str = ""
    message: str = ""
    post_id: str = ""
    campaign_id: str = ""
    content_id: str = ""
    content_type: str = ""  # REEL, POST, STORY, VIDEO, COMMENT

    # Extracted by router
    cta_keyword: str = ""
    intent: str = "unknown"
    pipeline: str = "seller"
    priority: str = "NORMAL"

    # Routing metadata
    routed_at: str = ""
    lead_id: str = ""
    first_response_at: str = ""
    qualified_at: str = ""

    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RoutingResult:
    """Result of routing a social interaction."""
    interaction_id: str
    intent: str
    pipeline: str
    priority: str
    cta_keyword: str
    confidence: float
    matched_keywords: List[str] = field(default_factory=list)
    recommended_action: str = ""
    lead_type: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class SocialCTARouter:
    """Routes social media interactions to the correct CRM pipeline."""

    def __init__(self, storage_path: Optional[Path] = None):
        self.storage_path = storage_path or (ROOT_DIR / "MBM" / "LeadEngine" / "social_interactions.json")
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.interactions: Dict[str, SocialInteraction] = {}
        self._load()

    def _load(self) -> None:
        if self.storage_path.exists():
            try:
                data = json.loads(self.storage_path.read_text(encoding="utf-8"))
                for item in data:
                    interaction = SocialInteraction(**item)
                    self.interactions[interaction.id] = interaction
            except Exception as e:
                print(f"[WARN] Error loading social interactions: {e}")

    def save(self) -> None:
        data = [i.to_dict() for i in self.interactions.values()]
        self.storage_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")

    def extract_intent(self, message: str) -> Tuple[IntentType, List[str], float]:
        """
        Extract intent from a social media message.
        Returns: (intent, matched_keywords, confidence)
        """
        if not message:
            return IntentType.UNKNOWN, [], 0.0

        message_upper = message.upper()
        matched = []
        scores: Dict[IntentType, int] = {intent: 0 for intent in IntentType}

        # Check each keyword
        for keyword, intent in CTA_KEYWORDS.items():
            if keyword in message_upper:
                matched.append(keyword)
                scores[intent] += 1

        # Find dominant intent
        if not matched:
            return IntentType.UNKNOWN, [], 0.0

        max_score = max(scores.values())
        if max_score == 0:
            return IntentType.UNKNOWN, matched, 0.0

        # Get intent with highest score
        dominant_intent = max(scores, key=lambda x: scores[x])

        # Confidence based on match count and specificity
        confidence = min(0.95, 0.3 + (len(matched) * 0.15) + (max_score * 0.1))

        return dominant_intent, matched, confidence

    def route_interaction(self, interaction: SocialInteraction) -> RoutingResult:
        """Route a social interaction to the correct pipeline."""
        intent, matched_keywords, confidence = self.extract_intent(interaction.message)

        # Determine pipeline
        pipeline = INTENT_TO_PIPELINE.get(intent, PipelineType.SELLER)

        # Determine priority
        priority = self._assess_priority(intent, interaction.message, matched_keywords)

        # Determine lead type
        lead_type = intent.value

        # Determine recommended action
        action = self._recommend_action(intent, priority)

        # Store CTA keyword
        cta_keyword = matched_keywords[0] if matched_keywords else ""

        # Update interaction
        interaction.cta_keyword = cta_keyword
        interaction.intent = intent.value
        interaction.pipeline = pipeline.value
        interaction.priority = priority.value
        interaction.routed_at = datetime.now(timezone.utc).isoformat()

        # Persist
        self.interactions[interaction.id] = interaction
        self.save()

        return RoutingResult(
            interaction_id=interaction.id,
            intent=intent.value,
            pipeline=pipeline.value,
            priority=priority.value,
            cta_keyword=cta_keyword,
            confidence=confidence,
            matched_keywords=matched_keywords,
            recommended_action=action,
            lead_type=lead_type,
        )

    def _assess_priority(self, intent: IntentType, message: str, keywords: List[str]) -> LeadPriority:
        """Assess lead priority based on intent and message content."""
        message_upper = message.upper() if message else ""

        # High priority signals
        high_signals = ["URGENT", "ASAP", "NEED TO SELL", "FORECLOSURE", "BEHIND ON PAYMENTS", "DIVORCE", "INHERITED"]
        if any(signal in message_upper for signal in high_signals):
            return LeadPriority.HOT

        # Deal sources with specific keywords are warm+
        if intent == IntentType.DEAL_SOURCE:
            if any(kw in message_upper for kw in ["UNDER CONTRACT", "HAVE A DEAL", "CONTRACT"]):
                return LeadPriority.HOT
            return LeadPriority.WARM

        # Buyers with funding signals
        if intent == IntentType.BUYER:
            if any(kw in message_upper for kw in ["CASH", "FUNDED", "READY TO BUY"]):
                return LeadPriority.WARM
            return LeadPriority.NORMAL

        # Sellers
        if intent == IntentType.SELLER:
            return LeadPriority.WARM

        # Partners
        if intent == IntentType.PARTNER:
            return LeadPriority.NORMAL

        return LeadPriority.NORMAL

    def _recommend_action(self, intent: IntentType, priority: LeadPriority) -> str:
        """Recommend next action based on intent and priority."""
        actions = {
            (IntentType.DEAL_SOURCE, LeadPriority.HOT): "SUBMIT_DEAL_FORM_NOW",
            (IntentType.DEAL_SOURCE, LeadPriority.WARM): "REQUEST_PROPERTY_DETAILS",
            (IntentType.DEAL_SOURCE, LeadPriority.NORMAL): "QUALIFY_DEAL_SOURCE",
            (IntentType.SELLER, LeadPriority.HOT): "CALL_NOW",
            (IntentType.SELLER, LeadPriority.WARM): "SEND_QUALIFICATION_QUESTIONS",
            (IntentType.SELLER, LeadPriority.NORMAL): "SCHEDULE_FOLLOWUP",
            (IntentType.BUYER, LeadPriority.HOT): "SEND_MATCHED_DEALS",
            (IntentType.BUYER, LeadPriority.WARM): "CAPTURE_BUY_BOX",
            (IntentType.BUYER, LeadPriority.NORMAL): "QUALIFY_BUYER",
            (IntentType.PARTNER, LeadPriority.HOT): "SCHEDULE_JV_CALL",
            (IntentType.PARTNER, LeadPriority.WARM): "SEND_JV_INFO",
            (IntentType.PARTNER, LeadPriority.NORMAL): "ADD_TO_PARTNER_PIPELINE",
            (IntentType.INVESTOR, LeadPriority.WARM): "SEND_INVESTOR_DECK",
            (IntentType.INVESTOR, LeadPriority.NORMAL): "QUALIFY_INVESTOR",
        }
        return actions.get((intent, priority), "FOLLOW_UP_STANDARD")

    def get_interactions_by_pipeline(self, pipeline: str) -> List[SocialInteraction]:
        """Get all interactions routed to a specific pipeline."""
        return [i for i in self.interactions.values() if i.pipeline == pipeline]

    def get_hot_leads(self) -> List[SocialInteraction]:
        """Get all hot-priority interactions."""
        return [i for i in self.interactions.values() if i.priority == "HOT"]

    def get_attribution_data(self, lead_id: str) -> Optional[Dict[str, Any]]:
        """Get full attribution data for a lead (source → content → campaign)."""
        for interaction in self.interactions.values():
            if interaction.lead_id == lead_id:
                return {
                    "source_platform": interaction.platform,
                    "source_username": interaction.username,
                    "source_post_id": interaction.post_id,
                    "source_campaign_id": interaction.campaign_id,
                    "source_content_id": interaction.content_id,
                    "source_content_type": interaction.content_type,
                    "source_cta_keyword": interaction.cta_keyword,
                    "source_intent": interaction.intent,
                    "routed_at": interaction.routed_at,
                    "first_response_at": interaction.first_response_at,
                    "qualified_at": interaction.qualified_at,
                }
        return None
