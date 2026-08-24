"""
Viral clip intelligence — Phase 3 scoring fusion.

Combines speech, visuals, pacing, emotion, narrative structure, campaign niche,
and historical performance into a single ranked, explainable score. This is a
pure, deterministic function (no network) so it is fully testable offline and
serves as the candidate-ranking brain the runtime routes through.

Each candidate supplies raw sub-signals (already extracted upstream by the
speech/visual factories). The engine applies configurable weights, blends in a
historical-performance prior from the learning memory, and emits:

  - ranked clips (sorted, with confidence + reasons + timestamps)
  - recommended platform (best fit by platform_fit x niche)
  - why each clip scored (human-readable reasons)

The best clip is NOT simply the highest transcript score — pacing, emotion,
niche fit and history all move the ranking.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

DEFAULT_WEIGHTS = {
    "hook": 0.16,
    "curiosity": 0.12,
    "emotional_intensity": 0.12,
    "information_density": 0.10,
    "replay_value": 0.08,
    "retention_prediction": 0.14,
    "visual_quality": 0.08,
    "audio_quality": 0.06,
    "platform_fit": 0.07,
    "brand_fit": 0.04,
    "business_value": 0.03,
}


@dataclass
class ClipSignal:
    """Raw signals for one candidate clip (0..1 unless noted)."""
    clip_id: str
    hook: float = 0.5
    curiosity: float = 0.5
    emotional_intensity: float = 0.5
    information_density: float = 0.5
    replay_value: float = 0.5
    retention_prediction: float = 0.5
    visual_quality: float = 0.5
    audio_quality: float = 0.5
    platform_fit: float = 0.5
    brand_fit: float = 0.5
    business_value: float = 0.5
    start_ts: float = 0.0
    end_ts: float = 0.0
    transcript_window: str = ""
    niche: str = ""
    historical_score: float = 0.5  # prior from learning memory (0..1)

    def to_dict(self) -> dict:
        return {
            "clip_id": self.clip_id, "hook": self.hook, "curiosity": self.curiosity,
            "emotional_intensity": self.emotional_intensity,
            "information_density": self.information_density, "replay_value": self.replay_value,
            "retention_prediction": self.retention_prediction, "visual_quality": self.visual_quality,
            "audio_quality": self.audio_quality, "platform_fit": self.platform_fit,
            "brand_fit": self.brand_fit, "business_value": self.business_value,
            "start_ts": self.start_ts, "end_ts": self.end_ts,
            "transcript_window": self.transcript_window, "niche": self.niche,
            "historical_score": self.historical_score,
        }


@dataclass
class RankedClip:
    clip_id: str
    score: float
    confidence: float
    reasons: list[str]
    start_ts: float
    end_ts: float
    recommended_platform: str
    breakdown: dict

    def to_dict(self) -> dict:
        return {
            "clip_id": self.clip_id, "score": round(self.score, 4),
            "confidence": round(self.confidence, 4), "reasons": self.reasons,
            "start_ts": self.start_ts, "end_ts": self.end_ts,
            "recommended_platform": self.recommended_platform, "breakdown": self.breakdown,
        }


# Per-niche platform affinity (used to recommend a platform, not to gate).
NICHE_PLATFORM_AFFINITY = {
    "dark_stories": "youtube",
    "football_highlights": "tiktok",
    "cute_wholesome": "instagram",
    "plot_twists": "youtube",
    "tech_automation": "linkedin",
    "movie_recaps": "youtube",
    "business_finance": "linkedin",
    "islamic_content": "youtube",
    "construction_real_estate": "youtube",
}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


def _reason(name: str, value: float, weight: float) -> str:
    qual = "strong" if value >= 0.75 else ("good" if value >= 0.55 else ("weak" if value < 0.35 else "fair"))
    return f"{name} {qual} ({value:.2f})"


def score_clip(sig: ClipSignal, weights: Optional[dict] = None, niche: Optional[str] = None) -> RankedClip:
    w = dict(DEFAULT_WEIGHTS)
    if weights:
        w.update({k: float(v) for k, v in weights.items()})

    raw = {
        "hook": sig.hook, "curiosity": sig.curiosity,
        "emotional_intensity": sig.emotional_intensity,
        "information_density": sig.information_density, "replay_value": sig.replay_value,
        "retention_prediction": sig.retention_prediction, "visual_quality": sig.visual_quality,
        "audio_quality": sig.audio_quality, "platform_fit": sig.platform_fit,
        "brand_fit": sig.brand_fit, "business_value": sig.business_value,
    }
    # Blend historical prior into retention prediction (learning feedback loop).
    retention = _clamp(0.8 * sig.retention_prediction + 0.2 * sig.historical_score)
    raw["retention_prediction"] = retention

    total = 0.0
    reasons = []
    breakdown = {}
    for name, val in raw.items():
        contrib = w.get(name, 0.0) * val
        total += contrib
        breakdown[name] = round(val, 3)
        if w.get(name, 0.0) >= 0.10:
            reasons.append(_reason(name, val, w[name]))

    # Confidence: how many strong sub-signals corroborate the score.
    strong = sum(1 for v in raw.values() if v >= 0.7)
    weak = sum(1 for v in raw.values() if v < 0.3)
    confidence = _clamp(0.5 + 0.05 * (strong - weak))

    niche_key = niche or sig.niche
    rec_platform = NICHE_PLATFORM_AFFINITY.get(niche_key, "youtube")
    if sig.platform_fit >= 0.7:
        rec_platform = NICHE_PLATFORM_AFFINITY.get(niche_key, rec_platform)

    reasons = sorted(reasons, key=lambda r: r)[:5]
    reasons.append(f"historical prior: {sig.historical_score:.2f}")
    reasons.append(f"recommended platform: {rec_platform}")

    return RankedClip(
        clip_id=sig.clip_id, score=_clamp(total), confidence=confidence,
        reasons=reasons, start_ts=sig.start_ts, end_ts=sig.end_ts,
        recommended_platform=rec_platform, breakdown=breakdown,
    )


def rank_candidates(signals: list[ClipSignal], weights: Optional[dict] = None,
                    niche: Optional[str] = None) -> list[RankedClip]:
    ranked = [score_clip(s, weights, niche=niche) for s in signals]
    ranked.sort(key=lambda r: (r.score, r.confidence), reverse=True)
    return ranked
