"""Content/Reel -> OPPORTUNITY CARD analyzer with claim separation.

Rule-based extraction is the deterministic fallback and the offline default;
an LLM provider (providers.py) enriches when configured. A creator's revenue
claim is stored as CLAIMED, never VERIFIED, until external evidence exists.
"""
from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional

from .models import ClaimType, OpportunityCard, Signal, now_iso

_PRICE_RE = re.compile(
    r"\$\s?([0-9]{1,5}(?:,[0-9]{3})*(?:\.[0-9]{2})?)|([0-9]{1,5}(?:\.[0-9]{2})?)\s?(?:dollars|usd)\b",
    re.IGNORECASE)
_RECURRING_WORDS = ["per month", "monthly", "retainer", "recurring", "mrr",
                    "subscription", "per week", "a month"]
_BIZ_MODEL_HINTS = {
    "productized_service": ["service", "agency", "done for you", "dfy", "package"],
    "saas": ["saas", "software", "app", "platform", "dashboard"],
    "info_product": ["course", "ebook", "guide", "template", "community"],
    "arbitrage": ["flipping", "arbitrage", "resell"],
    "affiliate": ["affiliate", "commission", "referral"],
}
_TOOL_HINTS = ["chatgpt", "claude", "midjourney", "runway", "elevenlabs", "heygen",
               "zapier", "make.com", "notion", "canva", "capcut", "descript",
               "vapi", "retell", "gohighlevel"]
_AUDIENCE_HINTS = ["realtors", "real estate agents", "dentists", "lawyers",
                   "restaurants", "gyms", "coaches", "ecommerce", "local businesses",
                   "creators", "small business"]


def _extract_price(text: str) -> Optional[float]:
    m = _PRICE_RE.search(text)
    if not m:
        return None
    raw = (m.group(1) or m.group(2) or "").replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def classify_claims(text: str) -> List[Dict[str, Any]]:
    """Separate CLAIMED / INFERRED / VERIFIED. Revenue claims from content are
    CLAIMED by default; only externally checkable artifacts verify."""
    claims: List[Dict[str, Any]] = []
    for m in _PRICE_RE.finditer(text):
        snippet = text[max(0, m.start() - 60):m.end() + 40].replace("\n", " ").strip()
        ctype = ClaimType.CLAIMED
        if re.search(r"\b(invoice|paid me|screenshot|receipt|stripe|bank)\b",
                     snippet, re.IGNORECASE):
            ctype = ClaimType.INFERRED  # evidence claimed but not independently verified
        claims.append({"claim": f"price mention: {m.group(0)}",
                       "type": ctype.value,
                       "context": snippet,
                       "verified": ctype is ClaimType.VERIFIED})
    for kw in _RECURRING_WORDS:
        if kw in text.lower():
            claims.append({"claim": f"recurrence hint: '{kw}'", "type": ClaimType.INFERRED.value,
                           "context": "", "verified": False})
            break
    return claims


def analyze_content(text: str, source_url: str = "", source: str = "operator") -> OpportunityCard:
    sig_hash = hashlib.sha256(f"{source_url}|{text[:400]}".encode()).hexdigest()[:12]
    t = (text or "")
    low = t.lower()

    biz_model = ""
    for model, hints in _BIZ_MODEL_HINTS.items():
        if any(h in low for h in hints):
            biz_model = model
            break
    tools = [tool for tool in _TOOL_HINTS if tool in low]
    audience = next((a for a in _AUDIENCE_HINTS if a in low), "")
    price = _extract_price(t)
    recurring = any(k in low for k in _RECURRING_WORDS)
    automation = 80 if ("automat" in low or "ai" in low) else 45
    complexity = 30 if biz_model == "productized_service" else 60 if biz_model == "saas" else 45

    card = OpportunityCard(
        card_id=f"CARD-{sig_hash}",
        title=(t.strip().split("\n")[0][:70] or "Untitled opportunity"),
        business_model=biz_model or "unspecified",
        product_service=t.strip()[:200],
        target_customer=audience or "unspecified",
        acquisition_method="outbound" if any(k in low for k in ("cold", "dm", "outreach")) else "",
        fulfillment_method="ai_assisted" if automation >= 70 else "manual",
        tools_used=tools,
        claimed_price_usd=price,
        recurring_revenue=recurring,
        automation_potential=automation,
        demand_signal=f"single signal via {source}" if source_url == "" else f"content at {source_url}",
        operational_complexity=complexity,
        risks=["creator revenue claims unverified"] if price else [],
        dependencies=tools,
        evidence=classify_claims(t),
        source_signals=[sig_hash],
    )
    return card


def signals_to_cards(signals: List[Signal]) -> List[OpportunityCard]:
    cards = []
    for s in signals:
        body = s.body or s.title
        if not body:
            continue
        card = analyze_content(body, source_url=s.url, source=s.source)
        if not card.source_signals:
            card.source_signals = [s.signal_id]
        cards.append(card)
    return cards
