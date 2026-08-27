# Social to CRM — Routing Design

**Date:** 2026-08-27

---

## PURPOSE

Route social media interactions into the correct CRM pipeline based on intent keywords and context.

---

## PLATFORM ABSTRACTION

```python
SOCIAL_PLATFORMS = {
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
```

---

## CTA KEYWORD ROUTING

```python
CTA_KEYWORDS = {
    # Deal source signals
    "DEAL": "deal_source",
    "HAVE A DEAL": "deal_source",
    "CONTRACT": "deal_source",
    "WHOLESALE": "deal_source",

    # Seller signals
    "SELL": "seller",
    "SELL MY HOUSE": "seller",
    "SELLING": "seller",
    "MOTIVATED": "seller",
    "FORECLOSURE": "seller",
    "DIVORCE": "seller",
    "INHERITED": "seller",
    "FIRE": "seller",
    "ASSESSED": "seller",

    # Buyer signals
    "BUY": "buyer",
    "BUYING": "buyer",
    "INVESTOR": "buyer",
    "CASH BUYER": "buyer",
    "LOOKING FOR": "buyer",
    "FUNDING": "buyer",

    # JV signals
    "JV": "partner",
    "PARTNER": "partner",
    "JOINT VENTURE": "partner",
    "COLLAB": "partner",

    # Investment signals
    "INVEST": "investor",
    "INVESTMENT": "investor",
    "ROI": "investor",
    "PASSIVE INCOME": "investor",
}

DEFAULT_ROUTING = "seller"  # If no keyword match, default to seller
```

---

## INTAKE FORM

### Minimal Intake (Social DM)
```python
@dataclass
class SocialIntake:
    platform: str           # instagram, facebook, etc.
    username: str
    message: str
    cta_keyword: str        # Extracted from message
    intent: str             # seller, buyer, deal_source, partner
    timestamp: datetime
    post_id: str            # Original content that triggered interaction
    campaign_id: str        # If from tracked campaign
```

### Full Intake (Deal Submission)
```python
@dataclass
class DealIntake:
    # Contact
    contact_name: str
    contact_phone: str
    contact_email: str
    platform: str
    username: str

    # Property
    address: str
    city: str
    state: str
    zip_code: str
    property_type: str      # SFR, DUPLEX, etc.

    # Deal
    contract_status: str    # UNDER_CONTRACT, PENDING, OPTION_PERIOD
    asking_price: float
    contract_price: float   # If known
    arv: float              # If known
    estimated_repairs: float
    occupancy: str          # VACANT, OWNER_OCCUPIED, TENANT
    closing_date: date
    photos: List[str]       # URLs
    listing_url: str

    # Source
    source: str             # instagram, facebook, referral, etc.
    campaign_id: str
    content_id: str

    # JV
    assignment_fee: float   # If known
    jv_split: str           # "50/50", "60/40"
    seller_constraints: str
```

---

## ROUTING FLOW

```
Social Interaction
       │
       ▼
┌──────────────────┐
│ Extract Keyword   │
│ from message/text │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Route by Intent   │
│ DEAL → DealSource │
│ SELL → Seller     │
│ BUY → Buyer       │
│ JV → Partner      │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Create Lead       │
│ with source attrs │
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Score & Qualify   │
│ (motivation/intent)│
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│ Assign to Pipeline│
│ and Next Action   │
└──────────────────┘
```

---

## ATTRIBUTION FIELDS

Every lead routed from social carries:
```python
{
    "source_platform": "instagram",
    "source_username": "@olivia_schremmer_fan",
    "source_post_id": "abc123",
    "source_campaign_id": "campaign_456",
    "source_content_type": "REEL",
    "source_cta_keyword": "DEAL",
    "source_intent": "deal_source",
    "routed_at": "2026-08-27T10:30:00Z",
    "first_response_at": null,
    "qualified_at": null,
    "first_deal_at": null,
    "first_revenue_at": null,
}
```

This enables full content → lead → deal → revenue attribution.
