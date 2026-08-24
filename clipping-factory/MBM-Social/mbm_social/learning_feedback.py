"""
learning_feedback -- Enterprise Memory learning loop (Phase 8).

Feeds completed clip results and actual analytics back into the learning engine
(Enterprise Memory = LearningMemory.json) and reads winning patterns back out to
improve future generation + routing. Pure I/O against the existing learning
engine; no new data store.
"""
from __future__ import annotations

from typing import Any, Optional

from . import learning_engine as le


def record_clip(clip_id: str, brand: str, profile: str, *, hook: str = "",
                title: str = "", caption: str = "", thumbnail_text: str = "",
                posting_time: str = "", source_url: str = "",
                platform: str = "youtube_shorts") -> None:
    """Persist one published clip to Enterprise Memory."""
    le.record_campaign_result(
        clip_id=clip_id, brand=brand, profile=profile, hook_text=hook,
        title=title, caption=caption, thumbnail_text=thumbnail_text,
        posting_time=posting_time, source_url=source_url, platform=platform,
    )


def record_analytics(clip_id: str, views: int, ctr: float, watch_time: float,
                     subs: int, revenue: float) -> None:
    """Feed verified analytics back so priors improve."""
    le.update_performance_from_analytics(clip_id, views, ctr, watch_time, subs, revenue)


def _winning(fn_name: str, brand: Optional[str], limit: int = 10):
    fn = getattr(le, fn_name, None)
    if fn is None:
        return []
    try:
        return [h.get("value", "") for h in fn(brand)[:limit]]
    except Exception:
        return []


def get_winning_patterns(brand: Optional[str] = None) -> dict:
    """Read winning hooks/titles/captions to feed content_intelligence."""
    return {
        "hooks": _winning("get_winning_hooks", brand),
        "titles": _winning("get_winning_titles", brand),
        "captions": _winning("get_winning_captions", brand),
    }


def feed_batch(results: list[dict]) -> int:
    """Record a batch of clip results. Returns count recorded."""
    n = 0
    for r in results:
        try:
            record_clip(
                clip_id=r.get("clip_id", ""), brand=r.get("brand", ""),
                profile=r.get("profile", ""), hook=r.get("hook", ""),
                title=r.get("title", ""), caption=r.get("caption", ""),
                posting_time=r.get("publish_at", ""), source_url=r.get("source_url", ""),
                platform=r.get("platform", "youtube_shorts"),
            )
            n += 1
        except Exception:
            continue
    return n
