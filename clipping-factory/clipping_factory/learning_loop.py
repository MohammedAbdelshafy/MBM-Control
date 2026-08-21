"""
Learning Loop — feeds published clip performance back into movie selection.

Every published Twists Revealed clip records:
  movie, genre, hook, duration, creative_score, voice, visual_style,
  caption_style, publish_time, views, retention, likes, comments

Missing metrics are treated as unknown, NOT as zero.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


LEARNING_FILE = Path(__file__).parent.parent / "artifacts" / "clipping_factory" / "learning_data.json"


@dataclass
class ClipPerformance:
    campaign_id: str
    movie_title: str
    genres: List[str]
    hook_text: str
    duration_sec: float
    creative_score: float
    voice_id: str
    visual_style: str
    caption_style: str
    publish_time_utc: str = ""
    published_platforms: List[str] = field(default_factory=list)
    video_id: str = ""
    # Metrics (None = unknown, NOT zero)
    views: Optional[int] = None
    retention_pct: Optional[float] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    subscriber_gain: Optional[int] = None
    watch_time_hours: Optional[float] = None
    recorded_at: str = ""

    def __post_init__(self):
        if not self.recorded_at:
            self.recorded_at = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _ensure_file():
    LEARNING_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not LEARNING_FILE.exists():
        LEARNING_FILE.write_text("[]", encoding="utf-8")


def record_performance(clip: ClipPerformance) -> None:
    """Record a published clip's performance data."""
    _ensure_file()
    try:
        data = json.loads(LEARNING_FILE.read_text(encoding="utf-8"))
    except Exception:
        data = []

    data.append(clip.to_dict())
    LEARNING_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def get_all_performances() -> List[Dict[str, Any]]:
    """Load all recorded performance data."""
    _ensure_file()
    try:
        return json.loads(LEARNING_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def get_genre_performance() -> Dict[str, Dict[str, Any]]:
    """Aggregate performance by genre."""
    clips = get_all_performances()
    genre_stats: Dict[str, Dict[str, Any]] = {}

    for clip in clips:
        for genre in clip.get("genres", ["unknown"]):
            if genre not in genre_stats:
                genre_stats[genre] = {
                    "count": 0,
                    "total_views": 0,
                    "total_likes": 0,
                    "total_comments": 0,
                    "avg_creative_score": 0.0,
                    "views_known": 0,
                }
            stats = genre_stats[genre]
            stats["count"] += 1
            stats["avg_creative_score"] += clip.get("creative_score", 0)

            views = clip.get("views")
            if views is not None:
                stats["total_views"] += views
                stats["views_known"] += 1

            likes = clip.get("likes")
            if likes is not None:
                stats["total_likes"] += likes

            comments = clip.get("comments")
            if comments is not None:
                stats["total_comments"] += comments

    for genre, stats in genre_stats.items():
        if stats["count"] > 0:
            stats["avg_creative_score"] = round(stats["avg_creative_score"] / stats["count"], 2)
        if stats["views_known"] > 0:
            stats["avg_views"] = round(stats["total_views"] / stats["views_known"])
        else:
            stats["avg_views"] = None

    return genre_stats


def get_hook_performance() -> List[Dict[str, Any]]:
    """Rank hooks by performance (views when known)."""
    clips = get_all_performances()
    hook_data = []
    for clip in clips:
        views = clip.get("views")
        hook_data.append({
            "hook": clip.get("hook_text", ""),
            "movie": clip.get("movie_title", ""),
            "creative_score": clip.get("creative_score", 0),
            "views": views,
            "has_metrics": views is not None,
        })
    hook_data.sort(key=lambda x: x.get("views") or 0, reverse=True)
    return hook_data


def get_recommendations(count: int = 5) -> Dict[str, Any]:
    """
    Generate recommendations for future movie selection and hooks
    based on historical performance data.
    """
    genre_perf = get_genre_performance()
    hook_perf = get_hook_performance()

    # Top genres by average views
    ranked_genres = sorted(
        genre_perf.items(),
        key=lambda x: x[1].get("avg_views") or 0,
        reverse=True,
    )

    # Best hooks
    best_hooks = [h for h in hook_perf if h.get("has_metrics")][:count]

    recommendations = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_clips_analyzed": len(hook_perf),
        "top_genres": [
            {"genre": g, "avg_views": s.get("avg_views"), "count": s["count"]}
            for g, s in ranked_genres[:5]
        ],
        "best_hooks": best_hooks,
        "suggested_genres": [g for g, _ in ranked_genres[:3]],
        "note": "Missing metrics are treated as unknown, not zero",
    }

    return recommendations
