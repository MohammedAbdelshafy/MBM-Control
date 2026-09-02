"""
OpportunityEngine — INTELLIGENCE + AUDIENCE + CONTENT FIT + MONETIZATION FIT (§6-7).

opportunity_score =
  signal_strength + freshness + niche_relevance + audience_relevance
  + monetization_fit + content_feasibility - risk_penalty

Weights are configurable; adapters never hardcode business assumptions.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .types import IntelligenceEvent, AffiliateOffer, Opportunity, OpportunityStatus, Provenance

DEFAULT_WEIGHTS: Dict[str, float] = {
    "signal_strength": 0.25,
    "freshness": 0.20,
    "niche_relevance": 0.18,
    "audience_relevance": 0.12,
    "monetization_fit": 0.15,
    "content_feasibility": 0.10,
    "risk_penalty": 1.0,  # subtracted
}

@dataclass
class ScoringConfig:
    weights: Dict[str, float] = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    niche_keywords: List[str] = field(default_factory=list)
    audience_keywords: List[str] = field(default_factory=list)
    # freshness decay: 0-24h = 1.0, 24-72h = 0.6, 72h+ = 0.3
    fresh_hours: int = 24
    warm_hours: int = 72

    @classmethod
    def from_env(cls) -> "ScoringConfig":
        nk = [s.strip().lower() for s in (os.environ.get("INTELLIGENCE_NICHE_KEYWORDS", "") or "").split(",") if s.strip()]
        ak = [s.strip().lower() for s in (os.environ.get("INTELLIGENCE_AUDIENCE_KEYWORDS", "") or "").split(",") if s.strip()]
        return cls(niche_keywords=nk, audience_keywords=ak)

    @classmethod
    def for_tests(cls) -> "ScoringConfig":
        return cls(
            niche_keywords=["real estate", "wholesale", "clinic", "ai services"],
            audience_keywords=["investor", "homeowner", "clinic owner"],
        )


def _freshness_score(freshness_seconds: Optional[int], cfg: ScoringConfig) -> float:
    if freshness_seconds is None:
        return 0.5
    hrs = freshness_seconds / 3600
    if hrs <= cfg.fresh_hours:
        return 1.0
    if hrs <= cfg.warm_hours:
        return 0.6
    if hrs <= 168:
        return 0.3
    return 0.1

def _keyword_overlap(text: str, keywords: List[str]) -> float:
    if not keywords or not text:
        return 0.5
    tl = text.lower()
    hits = sum(1 for kw in keywords if kw in tl)
    return min(1.0, hits / max(1, len(keywords) * 0.5))

def score_event(
    evt: IntelligenceEvent,
    *,
    offer: Optional[AffiliateOffer] = None,
    cfg: Optional[ScoringConfig] = None,
    risk_penalty: float = 0.0,
) -> tuple[float, Dict[str, float]]:
    cfg = cfg or ScoringConfig.from_env()
    w = cfg.weights
    text = f"{evt.title} {evt.summary or ''} {' '.join(evt.topics)} {' '.join(evt.entities)}"

    signal_strength = float(evt.confidence or 0.6)  # 0..1
    freshness = _freshness_score(evt.freshnessSeconds, cfg)
    niche_relevance = _keyword_overlap(text, cfg.niche_keywords)
    audience_relevance = _keyword_overlap(text, cfg.audience_keywords)

    # monetization fit: does offer vertical overlap event topics?
    if offer is None:
        monetization_fit = 0.5  # neutral when no offer joined
    else:
        vert = (offer.vertical or "").lower()
        if vert and vert in text.lower():
            monetization_fit = 0.9
        elif offer.commissionRate and offer.commissionRate >= 0.3:
            monetization_fit = 0.7
        elif offer.status == "VERIFIED":
            monetization_fit = 0.6
        else:
            monetization_fit = 0.2

    # content feasibility: short title + clear category -> easier to produce
    content_feasibility = 0.8 if len(evt.title) < 120 and evt.category != "general" else 0.6

    breakdown = {
        "signal_strength": round(signal_strength * w["signal_strength"], 4),
        "freshness": round(freshness * w["freshness"], 4),
        "niche_relevance": round(niche_relevance * w["niche_relevance"], 4),
        "audience_relevance": round(audience_relevance * w["audience_relevance"], 4),
        "monetization_fit": round(monetization_fit * w["monetization_fit"], 4),
        "content_feasibility": round(content_feasibility * w["content_feasibility"], 4),
        "risk_penalty": round(risk_penalty * w["risk_penalty"], 4),
    }
    score = sum(v for k, v in breakdown.items() if k != "risk_penalty") - breakdown["risk_penalty"]
    # clamp 0..1
    score = max(0.0, min(1.0, score))
    return round(score, 4), breakdown


class OpportunityEngine:
    def __init__(self, cfg: Optional[ScoringConfig] = None):
        self.cfg = cfg or ScoringConfig.from_env()

    def rank(
        self,
        events: List[IntelligenceEvent],
        offers: Optional[List[AffiliateOffer]] = None,
        *,
        top_n: int = 20,
    ) -> List[Dict[str, Any]]:
        offers = offers or []
        # naive offer matching: pick best matching offer per event
        ranked: List[Dict[str, Any]] = []
        for evt in events:
            best_offer: Optional[AffiliateOffer] = None
            best_fit = -1
            for off in offers:
                _, br = score_event(evt, offer=off, cfg=self.cfg)
                fit = br.get("monetization_fit", 0)
                if fit > best_fit:
                    best_fit = fit
                    best_offer = off
            risk = 0.15 if evt.confidence and evt.confidence < 0.4 else 0.0
            score, breakdown = score_event(evt, offer=best_offer, cfg=self.cfg, risk_penalty=risk)
            
            # Map IntelligenceEvent provenance -> Opportunity provenance
            opp_prov = Provenance(
                provider=evt.provenance.provider,
                provider_object_id=evt.id,
                source_url=evt.sourceUrl or evt.provenance.sourceUrl,
                source_type="api_event",
                captured_at=evt.provenance.retrievedAt or datetime.now(timezone.utc).isoformat(),
                raw_metadata_hash=evt.id,
                content_hash=evt.id,
                transformation_lineage=[f"{evt.provenance.transform} -> opportunity_engine"] if evt.provenance.transform else ["opportunity_engine"],
                confidence=evt.confidence or evt.provenance.confidence or 0.6,
                tool=evt.provenance.tool,
                rawReference=evt.provenance.rawReference
            )
            
            opp = Opportunity(
                opportunity_id=f"opp_{evt.id}",
                source_event_id=evt.id,
                source_provider=evt.source,
                source_url=evt.sourceUrl,
                title=evt.title[:120],
                summary=(evt.summary or evt.title)[:200],
                niche=",".join(self.cfg.niche_keywords) if self.cfg.niche_keywords else evt.category,
                audience=",".join(self.cfg.audience_keywords),
                signal_score=breakdown.get("signal_strength", 0.0),
                freshness_score=breakdown.get("freshness", 0.0),
                monetization_score=breakdown.get("monetization_fit", 0.0),
                feasibility_score=breakdown.get("content_feasibility", 0.0),
                risk_score=breakdown.get("risk_penalty", 0.0),
                total_score=score,
                confidence=evt.confidence or 0.6,
                provenance=opp_prov,
                status=OpportunityStatus.SCORED
            )
            
            if not opp.is_provenance_complete():
                opp.status = OpportunityStatus.REVIEW_REQUIRED

            ranked.append({
                "opportunity": opp.__dict__,
                "event": evt.__dict__,
                "matched_offer": best_offer.to_dict() if best_offer else None,
                "score": score,
                "breakdown": breakdown,
            })
        ranked.sort(key=lambda x: x["score"], reverse=True)
        return ranked[:top_n]
