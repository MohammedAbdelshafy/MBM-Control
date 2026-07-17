"""
BrandRouter — selects the correct channel for a clip.

Scoring (weights from CampaignRouter.json):
  topic_match, hook_style_match, visual_fit, keyword_overlap, past_performance
Topic/hook matching uses local embeddings + a local LLM classification,
never a hardcoded single model.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Optional

from . import model_registry as mr
from . import brand_config as bc


@dataclass
class RouteResult:
    brand: str
    channel_id: str
    handle: str
    score: float
    breakdown: dict
    needs_review: bool
    reason: str


def _text_of(candidate: dict) -> str:
    parts = [
        candidate.get("transcript_window") or "",
        " ".join(candidate.get("tags") or []),
        candidate.get("reason") or "",
        candidate.get("type") or "",
    ]
    return " ".join(p for p in parts if p).strip()


def _keyword_overlap(text: str, keywords: list[str]) -> float:
    if not keywords:
        return 0.0
    low = text.lower()
    hits = sum(1 for k in keywords if k.lower() in low)
    return hits / len(keywords)


def _embedding_sim(text: str, brand_theme: str, keywords: list[str]) -> float:
    try:
        ref = f"{brand_theme}. Keywords: {', '.join(keywords)}"
        a = mr.embed(text)
        b = mr.embed(ref)
        return mr.cosine(a, b)
    except Exception:
        return 0.0


def _llm_topic_match(text: str, eligible: list[str], exclude: list[str], emb_sim: float = 0.0) -> float:
    if not text:
        return 0.0
    # LLM-based routing is opt-in (slow on CPU). Default: use embedding proxy.
    import os
    if os.environ.get("MBM_LLM_ROUTING") != "1":
        return max(emb_sim, 0.4)
    sys = ("You are a strict content classifier for a multi-channel network. "
           "Decide how well the clip fits the brand's eligible topics. "
           "Reply with only a number from 0.0 to 1.0.")
    prompt = (
        f"Eligible topics: {', '.join(eligible)}.\n"
        f"Excluded topics: {', '.join(exclude)}.\n"
        f"Clip text: '''{text[:1200]}'''\n"
        f"If the clip is clearly in an excluded topic, return 0.0. "
        f"If strongly eligible, return >=0.8. Return the score only."
    )
    try:
        out = mr.generate(prompt, task="topic_classification", system=sys, max_tokens=8)
        return float(out.strip().split()[0])
    except Exception:
        # Fall back to embedding similarity so scoring stays meaningful.
        return max(emb_sim, 0.4)


def route_clip(candidate: dict) -> RouteResult:
    router = bc.load_campaign_router()
    weights = router.get("scoring_weights", {})
    rules = {r["brand"]: r for r in router.get("rules", [])}
    text = _text_of(candidate)
    hook_style = (candidate.get("hook_style") or "").lower()

    results = []
    for brand in bc.active_brands():
        # BrandRegistry entries carry config_path -> "Brands/<slug>/"
        slug = (brand.get("config_path") or "").strip("/").split("/")[-1] or brand.get("display_name")
        rule = rules.get(slug, {})
        cfg = _safe_load(slug)
        if cfg is None:
            continue
        kw = cfg.get("keywords", [])
        theme = cfg.get("theme", "")
        eligible = rule.get("eligible_topics", [])
        exclude = rule.get("exclude_topics", [])

        emb_sim = _embedding_sim(text, theme, kw)
        topic_match = _llm_topic_match(text, eligible, exclude, emb_sim)
        kw_overlap = _keyword_overlap(text, kw)
        hook_match = 1.0 if hook_style and hook_style in (cfg.get("hook_style", "").lower()) else 0.4
        visual_fit = 0.7  # placeholder; refined once thumbnail analysis (llava) is wired

        score = (
            weights.get("topic_match", 0.4) * topic_match
            + weights.get("hook_style_match", 0.2) * hook_match
            + weights.get("visual_fit", 0.15) * visual_fit
            + weights.get("keyword_overlap", 0.15) * kw_overlap
            + weights.get("past_performance", 0.1) * 0.5
        )
        ch = bc.channel_for_brand(slug)
        results.append({
            "brand": slug,
            "channel_id": ch["youtube_channel_id"] if ch else "",
            "handle": ch["handle"] if ch else "",
            "score": round(score, 4),
            "breakdown": {
                "topic_match": round(topic_match, 3),
                "hook_style_match": round(hook_match, 3),
                "visual_fit": round(visual_fit, 3),
                "keyword_overlap": round(kw_overlap, 3),
                "embedding_sim": round(emb_sim, 3),
            },
        })

    results.sort(key=lambda r: r["score"], reverse=True)
    best = results[0] if results else None
    if best is None:
        return RouteResult("", "", "", 0.0, {}, True, "no brands available")

    needs_review = best["score"] < 0.65
    reason = (
        f"Best brand '{best['brand']}' scored {best['score']:.2f} "
        f"(topic={best['breakdown']['topic_match']}, kw_overlap={best['breakdown']['keyword_overlap']}, "
        f"emb={best['breakdown']['embedding_sim']})."
    )
    if needs_review:
        reason += " Below 0.65 -> flagged for manual review."

    return RouteResult(
        brand=best["brand"],
        channel_id=best["channel_id"],
        handle=best["handle"],
        score=best["score"],
        breakdown=best["breakdown"],
        needs_review=needs_review,
        reason=reason,
    )


def _safe_load(slug: str):
    try:
        return bc.load_brand(slug)
    except Exception:
        return None


def route_clip_dict(candidate: dict) -> dict:
    r = route_clip(candidate)
    return asdict(r)
