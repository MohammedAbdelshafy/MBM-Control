"""
candidate_pool -- Crayo-class candidate generation + multi-factor scoring (Phase 1).

Turns ONE authorized long-form source into a LARGE candidate pool, scores every
candidate on the eight required axes, and selects the publishable subset.

Reuses the existing ClipScorer brain in `viral_intelligence` (score_clip) so the
scoring math stays in ONE place and remains deterministic/testable. The eight
required per-candidate fields are produced here by mapping the ClipScorer
breakdown plus speech/caption sub-signals we attach:

    hook_score
    speech_score
    visual_score
    retention_prediction
    platform_fit
    brand_fit
    caption_quality
    overall_score

Candidate *generation* is a planning step: given a source and a target pool size
(10/25/50/100/250) it lays out candidate windows. Real segmentation (actual ffmpeg
cuts, faster-whisper word alignment) happens downstream in the editing stage; the
pool here works on segment specs so the logic is testable without media.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from . import viral_intelligence as vi

# Configurable pool sizes required by the brief.
POOL_SIZES = (10, 25, 50, 100, 250)


@dataclass
class PoolConfig:
    """How large a candidate pool to build and what thresholds to apply."""
    size: int = 50  # one of POOL_SIZES
    source_duration_s: float = 600.0
    niche: str = ""
    brand: str = ""
    # selection thresholds applied after scoring
    min_overall_score: float = 0.45
    min_hook_score: float = 0.40
    min_predicted_retention: float = 0.40
    publishable_target: int = 10  # how many to promote to the publish queue

    def __post_init__(self) -> None:
        if self.size not in POOL_SIZES:
            # clamp to nearest allowed size instead of failing
            self.size = min(POOL_SIZES, key=lambda s: abs(s - self.size))


@dataclass
class Candidate:
    clip_id: str
    source_id: str
    start_ts: float
    end_ts: float
    scores: dict  # the eight required axes + any extras
    recommended_platform: str
    selected: bool = False
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "clip_id": self.clip_id,
            "source_id": self.source_id,
            "start_ts": self.start_ts,
            "end_ts": self.end_ts,
            "scores": self.scores,
            "recommended_platform": self.recommended_platform,
            "selected": self.selected,
            "reasons": self.reasons,
        }


def _default_signal(i: int, duration_s: float, size: int) -> vi.ClipSignal:
    """Deterministic synthetic candidate signal for pool planning.

    Real signals (hook strength, speech clarity, visual quality) are produced
    downstream by the speech/visual factories; here we lay out an even grid so
    the selection math is exercised deterministically in tests and dry-runs.
    """
    step = max(1.0, duration_s / max(1, size))
    start = round(i * step, 2)
    end = round(min(duration_s, start + step), 2)
    # light pseudo-variation so ranking isn't flat
    phase = (i * 0.137) % 1.0
    base = 0.35 + 0.3 * phase
    return vi.ClipSignal(
        clip_id=f"cand_{i:04d}",
        hook=round(min(1.0, base + 0.1), 3),
        curiosity=round(min(1.0, base), 3),
        emotional_intensity=round(min(1.0, 0.4 + 0.4 * ((i * 0.31) % 1.0)), 3),
        information_density=round(min(1.0, 0.45 + 0.35 * ((i * 0.17) % 1.0)), 3),
        replay_value=round(min(1.0, 0.4 + 0.3 * ((i * 0.23) % 1.0)), 3),
        retention_prediction=round(min(1.0, 0.45 + 0.35 * ((i * 0.29) % 1.0)), 3),
        visual_quality=round(min(1.0, 0.5 + 0.3 * ((i * 0.11) % 1.0)), 3),
        audio_quality=round(min(1.0, 0.6 + 0.2 * ((i * 0.07) % 1.0)), 3),
        platform_fit=round(min(1.0, 0.5 + 0.3 * ((i * 0.19) % 1.0)), 3),
        brand_fit=round(min(1.0, 0.55 + 0.25 * ((i * 0.13) % 1.0)), 3),
        business_value=round(min(1.0, 0.4 + 0.3 * ((i * 0.05) % 1.0)), 3),
        start_ts=start,
        end_ts=end,
        transcript_window=f"segment {i} around {start:.0f}s",
        niche="",
        historical_score=round(min(1.0, 0.4 + 0.2 * ((i * 0.37) % 1.0)), 3),
    )


def _build_candidate(sig: vi.ClipSignal, cfg: PoolConfig,
                     weights: Optional[dict], caption_quality: float) -> Candidate:
    ranked = vi.score_clip(sig, weights=weights, niche=cfg.niche or None)
    speech_score = round(min(1.0, 0.5 * sig.information_density + 0.5 * sig.emotional_intensity), 3)
    scores = {
        "hook_score": round(float(ranked.breakdown.get("hook", sig.hook)), 3),
        "speech_score": speech_score,
        "visual_score": round(float(ranked.breakdown.get("visual_quality", sig.visual_quality)), 3),
        "retention_prediction": round(float(ranked.breakdown.get("retention_prediction", sig.retention_prediction)), 3),
        "platform_fit": round(float(ranked.breakdown.get("platform_fit", sig.platform_fit)), 3),
        "brand_fit": round(float(ranked.breakdown.get("brand_fit", sig.brand_fit)), 3),
        "caption_quality": round(float(caption_quality), 3),
        "overall_score": round(float(ranked.score), 4),
    }
    return Candidate(
        clip_id=sig.clip_id,
        source_id=cfg.brand and cfg.brand or "source",
        start_ts=sig.start_ts,
        end_ts=sig.end_ts,
        scores=scores,
        recommended_platform=ranked.recommended_platform,
        reasons=ranked.reasons,
    )


def generate_candidates(source_id: str, *, cfg: Optional[PoolConfig] = None,
                        segments: Optional[list[dict]] = None,
                        weights: Optional[dict] = None,
                        caption_quality: float = 0.6) -> list[Candidate]:
    """Build a scored candidate pool from one source.

    `segments` is an optional list of pre-extracted segment specs
    ({"start_ts", "end_ts", ...raw signals...}). If omitted, an even grid of
    `cfg.size` candidate windows is planned across the source duration.
    """
    cfg = cfg or PoolConfig()
    if segments:
        sigs = []
        for i, seg in enumerate(segments):
            sig = vi.ClipSignal(
                clip_id=seg.get("clip_id") or f"cand_{i:04d}",
                hook=float(seg.get("hook", 0.5)),
                curiosity=float(seg.get("curiosity", 0.5)),
                emotional_intensity=float(seg.get("emotional_intensity", 0.5)),
                information_density=float(seg.get("information_density", 0.5)),
                replay_value=float(seg.get("replay_value", 0.5)),
                retention_prediction=float(seg.get("retention_prediction", 0.5)),
                visual_quality=float(seg.get("visual_quality", 0.5)),
                audio_quality=float(seg.get("audio_quality", 0.5)),
                platform_fit=float(seg.get("platform_fit", 0.5)),
                brand_fit=float(seg.get("brand_fit", 0.5)),
                business_value=float(seg.get("business_value", 0.5)),
                start_ts=float(seg.get("start_ts", 0.0)),
                end_ts=float(seg.get("end_ts", 0.0)),
                transcript_window=seg.get("transcript_window", ""),
                niche=cfg.niche,
                historical_score=float(seg.get("historical_score", 0.5)),
            )
            sigs.append(sig)
    else:
        sigs = [_default_signal(i, cfg.source_duration_s, cfg.size) for i in range(cfg.size)]
        # override source id so it reflects the real one
    for s in sigs:
        s.niche = cfg.niche

    candidates = [_build_candidate(s, cfg, weights, caption_quality) for s in sigs]
    for c in candidates:
        c.source_id = source_id
    candidates.sort(key=lambda c: c.scores["overall_score"], reverse=True)
    return candidates


def select_publishable(candidates: list[Candidate], cfg: PoolConfig) -> list[Candidate]:
    """Apply quality gates and the publishable cap. Mutates `.selected`."""
    promoted = 0
    for c in candidates:
        s = c.scores
        ok = (
            s["overall_score"] >= cfg.min_overall_score
            and s["hook_score"] >= cfg.min_hook_score
            and             s["retention_prediction"] >= cfg.min_predicted_retention
        )
        if ok and promoted < cfg.publishable_target:
            c.selected = True
            promoted += 1
        else:
            pass  # not selected
    return [c for c in candidates if c.selected]
