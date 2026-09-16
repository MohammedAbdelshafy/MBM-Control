"""Opportunity deduplication/clustering + trend velocity.

Many Reels about 'AI realtor videos' must become ONE opportunity cluster
(REAL_ESTATE_AI_MEDIA) with N independent evidence sources — never 4 shiny
objects."""
from __future__ import annotations

import re
from datetime import datetime
from typing import Dict, List, Tuple

from .models import Opportunity, OpportunityCard, Velocity

_STOP = set("the a an and or of to for with your you my we it is are in on at how this that "
            "from make money using ai".split())

_CANONICAL_NAMES = {
    ("realtor", "real estate", "listing", "property"): "REAL_ESTATE_AI_MEDIA",
    ("dubbing", "translation", "multilingual"): "MULTILINGUAL_CONTENT_LOCALIZATION",
    ("lead", "prospecting", "outbound"): "AI_LEAD_GEN_SERVICES",
}


def _tokens(text: str) -> set:
    words = re.findall(r"[a-z]{3,}", (text or "").lower())
    return {w for w in words if w not in _STOP}


def canonical_cluster_name(text: str) -> str:
    low = (text or "").lower()
    for keys, name in _CANONICAL_NAMES.items():
        if sum(1 for k in keys if k in low) >= 2:
            return name
    toks = sorted(_tokens(low))[:3]
    return "_".join(toks).upper() or "UNCATEGORIZED"


def similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def cluster_card(card: OpportunityCard, existing: List[Opportunity],
                 threshold: float = 0.34) -> Opportunity:
    probe = f"{card.title} {card.product_service} {card.target_customer}"
    # 1) canonical named clusters merge first (REAL_ESTATE_AI_MEDIA etc.)
    name = canonical_cluster_name(probe)
    for opp in existing:
        if opp.cluster_name == name:
            opp.add_evidence(card, source=card.demand_signal.split(" via ")[-1])
            return opp
    # 2) fuzzy token-similarity fallback for unnamed topics
    best: Tuple[float, Opportunity | None] = (0.0, None)
    for opp in existing:
        rep = f"{opp.title} {opp.cards[0].product_service if opp.cards else ''}"
        sim = similarity(probe, rep)
        if sim > best[0]:
            best = (sim, opp)
    if best[1] is not None and best[0] >= threshold:
        best[1].add_evidence(card, source=card.demand_signal.split(" via ")[-1])
        return best[1]
    opp = Opportunity(
        opportunity_id=f"OPP-{name[:40]}-{len(existing)+1:03d}",
        cluster_name=name,
        title=card.title,
    )
    opp.add_evidence(card, source=card.demand_signal.split(" via ")[-1])
    existing.append(opp)
    return opp


def velocity(opp: Opportunity, now: datetime | None = None) -> Velocity:
    """Classify trend from signal count, recency and active window."""
    now = now or datetime.now().astimezone()
    days_active = max((now - datetime.fromisoformat(opp.first_seen)).days, 0) + 1
    rate = opp.signal_count / days_active
    recency_days = max((now - datetime.fromisoformat(opp.last_seen)).days, 0)
    if opp.signal_count < 2:
        v = Velocity.EMERGING
    elif recency_days > 21:
        v = Velocity.SATURATED
    elif recency_days > 14:
        v = Velocity.DECLINING
    elif recency_days <= 1 and rate >= 0.75:
        v = Velocity.ACCELERATING
    else:
        v = Velocity.STABLE
    opp.velocity = v.value
    return v
