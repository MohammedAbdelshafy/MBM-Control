"""
Learning Engine — self-improving system that tracks what works and updates
future ranking, hook generation, posting times, and source selection.

Stores:
  Views, CTR, Watch Time, Subscribers, Revenue
  Winning Hooks, Titles, Captions, Thumbnails, Posting Times, Sources

Updates CampaignRouter.json scoring weights and brand configs automatically.
All data stored in LearningMemory.json — no database writes for learning.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent

MEMORY_PATH = ROOT / "LearningMemory.json"
METRICS_PATH = ROOT / "ChannelMetrics.json"
ROUTER_PATH = ROOT / "CampaignRouter.json"


def _load_memory() -> dict:
    if MEMORY_PATH.exists():
        return json.loads(MEMORY_PATH.read_text(encoding="utf-8"))
    return {
        "version": 1,
        "updated": datetime.now().isoformat(),
        "campaigns": [],
        "winning_hooks": {},
        "winning_titles": {},
        "winning_captions": {},
        "winning_thumbnails": {},
        "winning_posting_times": {},
        "winning_sources": {},
        "brand_performance": {},
        "profile_performance": {},
        "platform_performance": {},
    }


def _save_memory(memory: dict):
    memory["updated"] = datetime.now().isoformat()
    MEMORY_PATH.write_text(json.dumps(memory, indent=2, ensure_ascii=False), encoding="utf-8")


def _load_metrics() -> dict:
    if METRICS_PATH.exists():
        return json.loads(METRICS_PATH.read_text(encoding="utf-8"))
    return {"channels": {}, "clip_history": [], "network_rollup": {}}


def _load_router() -> dict:
    if ROUTER_PATH.exists():
        return json.loads(ROUTER_PATH.read_text(encoding="utf-8"))
    return {}


def record_campaign_result(
    clip_id: str,
    brand: str,
    profile: str,
    hook_text: str = "",
    title: str = "",
    caption: str = "",
    thumbnail_text: str = "",
    posting_time: str = "",
    source_url: str = "",
    platform: str = "youtube_shorts",
):
    """Record a completed campaign result for learning."""
    memory = _load_memory()

    entry = {
        "clip_id": clip_id,
        "brand": brand,
        "profile": profile,
        "hook_text": hook_text,
        "title": title,
        "caption": caption,
        "thumbnail_text": thumbnail_text,
        "posting_time": posting_time,
        "source_url": source_url,
        "platform": platform,
        "timestamp": datetime.now().isoformat(),
        "views": 0,
        "ctr": 0.0,
        "watch_time_sec": 0.0,
        "subs_gain": 0,
        "revenue_usd": 0.0,
        "status": "published",
    }

    memory["campaigns"].append(entry)

    # Trim to last 2000 entries
    memory["campaigns"] = memory["campaigns"][-2000:]

    # Update winning pattern caches
    if hook_text:
        _update_winning(memory, "winning_hooks", brand, hook_text)
    if title:
        _update_winning(memory, "winning_titles", brand, title)
    if caption:
        _update_winning(memory, "winning_captions", brand, caption)
    if thumbnail_text:
        _update_winning(memory, "winning_thumbnails", brand, thumbnail_text)
    if posting_time:
        hour = posting_time.split("T")[1][:2] if "T" in posting_time else ""
        if hour:
            _update_winning(memory, "winning_posting_times", brand, hour)
    if source_url:
        _update_winning(memory, "winning_sources", brand, source_url)

    # Update brand performance
    bp = memory.setdefault("brand_performance", {}).setdefault(brand, {
        "total_campaigns": 0, "total_views": 0, "avg_ctr": 0.0,
        "total_revenue": 0.0, "best_hook": "", "best_title": "",
    })
    bp["total_campaigns"] += 1

    # Update profile performance
    pp = memory.setdefault("profile_performance", {}).setdefault(profile, {
        "total_campaigns": 0, "total_views": 0, "avg_ctr": 0.0,
    })
    pp["total_campaigns"] += 1

    _save_memory(memory)


def update_performance_from_analytics(clip_id: str, views: int, ctr: float,
                                       watch_time: float, subs: int, revenue: float):
    """Update learning memory with actual performance data from analytics."""
    memory = _load_memory()

    for entry in memory["campaigns"]:
        if entry.get("clip_id") == clip_id:
            entry["views"] = views
            entry["ctr"] = ctr
            entry["watch_time_sec"] = watch_time
            entry["subs_gain"] = subs
            entry["revenue_usd"] = revenue

            brand = entry.get("brand", "")
            if brand in memory.get("brand_performance", {}):
                bp = memory["brand_performance"][brand]
                bp["total_views"] = bp.get("total_views", 0) + views
                bp["total_revenue"] = bp.get("total_revenue", 0) + revenue
                # Update running average CTR
                n = bp["total_campaigns"]
                bp["avg_ctr"] = ((bp.get("avg_ctr", 0) * (n - 1)) + ctr) / n if n > 0 else ctr

                # Track winning patterns by performance
                if views > 10000:
                    if entry.get("hook_text"):
                        bp["best_hook"] = entry["hook_text"]
                    if entry.get("title"):
                        bp["best_title"] = entry["title"]
            break

    _save_memory(memory)


def _update_winning(memory: dict, category: str, brand: str, value: str):
    """Increment count for a winning pattern."""
    cat = memory.setdefault(category, {})
    brand_cat = cat.setdefault(brand, {})
    brand_cat[value] = brand_cat.get(value, 0) + 1


def get_winning_hooks(brand: Optional[str] = None, limit: int = 10) -> list[dict]:
    """Return top-performing hooks for a brand or all brands."""
    memory = _load_memory()
    hooks = memory.get("winning_hooks", {})

    if brand:
        brand_hooks = hooks.get(brand, {})
    else:
        brand_hooks = {}
        for b, h in hooks.items():
            for hook, count in h.items():
                brand_hooks[hook] = brand_hooks.get(hook, 0) + count

    sorted_hooks = sorted(brand_hooks.items(), key=lambda x: x[1], reverse=True)
    return [{"hook": h, "count": c} for h, c in sorted_hooks[:limit]]


def get_winning_titles(brand: Optional[str] = None, limit: int = 10) -> list[dict]:
    memory = _load_memory()
    titles = memory.get("winning_titles", {})
    if brand:
        brand_titles = titles.get(brand, {})
    else:
        brand_titles = {}
        for b, t in titles.items():
            for title, count in t.items():
                brand_titles[title] = brand_titles.get(title, 0) + count
    sorted_titles = sorted(brand_titles.items(), key=lambda x: x[1], reverse=True)
    return [{"title": t, "count": c} for t, c in sorted_titles[:limit]]


def get_best_posting_times(brand: Optional[str] = None) -> dict:
    """Return best posting hours for a brand."""
    memory = _load_memory()
    times = memory.get("winning_posting_times", {})

    if brand:
        return times.get(brand, {})
    else:
        combined = {}
        for b, t in times.items():
            for hour, count in t.items():
                combined[hour] = combined.get(hour, 0) + count
        return combined


def get_brand_performance_summary() -> dict:
    """Return performance summary for all brands."""
    memory = _load_memory()
    return memory.get("brand_performance", {})


def get_learning_insights(brand: Optional[str] = None) -> dict:
    """Generate actionable insights from learning data."""
    memory = _load_memory()
    insights = {
        "generated_at": datetime.now().isoformat(),
        "total_campaigns": len(memory.get("campaigns", [])),
        "brands_active": len(memory.get("brand_performance", {})),
        "recommendations": [],
    }

    bp = memory.get("brand_performance", {})
    for b, perf in bp.items():
        if brand and b != brand:
            continue
        total = perf.get("total_campaigns", 0)
        if total < 5:
            insights["recommendations"].append({
                "brand": b,
                "type": "data_collection",
                "message": f"Only {total} campaigns for {b}. Need more data for reliable learning.",
            })
            continue

        avg_ctr = perf.get("avg_ctr", 0)
        if avg_ctr < 0.04:
            insights["recommendations"].append({
                "brand": b,
                "type": "hook_optimization",
                "message": f"CTR for {b} is {avg_ctr:.3f} (below 4% target). Test new hook styles.",
            })

        if perf.get("total_views", 0) / max(total, 1) < 1000:
            insights["recommendations"].append({
                "brand": b,
                "type": "content_relevance",
                "message": f"Avg views per clip for {b} is low. Review topic targeting and posting times.",
            })

    return insights


def auto_update_scoring_weights():
    """Auto-update CampaignRouter.json scoring weights based on learning data.

    This adjusts the weights in the scoring model based on what's actually
    driving performance across the network.
    """
    memory = _load_memory()
    router = json.loads(ROUTER_PATH.read_text(encoding="utf-8")) if ROUTER_PATH.exists() else {}

    campaigns = memory.get("campaigns", [])
    if len(campaigns) < 20:
        return {"updated": False, "reason": "insufficient_data"}

    # Analyze which factors correlate with high-performing clips
    high_performers = [c for c in campaigns if c.get("views", 0) > 5000]
    low_performers = [c for c in campaigns if c.get("views", 0) < 1000 and c.get("views", 0) > 0]

    current_weights = router.get("scoring_weights", {})

    # If high performers tend to have specific hook styles, increase hook_weight
    if len(high_performers) > 5:
        hook_diversity = len(set(c.get("hook_text", "")[:20] for c in high_performers))
        if hook_diversity > 3:
            # Diverse hooks work — maintain or slightly increase hook weight
            current_weights["hook_style_match"] = min(0.25, current_weights.get("hook_style_match", 0.20) + 0.02)
        # Narrow topic focus in high performers → increase topic weight
        topic_concentration = len(set(c.get("brand", "") for c in high_performers)) / max(len(high_performers), 1)
        if topic_concentration < 0.5:
            current_weights["topic_match"] = min(0.50, current_weights.get("topic_match", 0.40) + 0.03)

    # Normalize weights to sum to 1.0
    total = sum(current_weights.values())
    if total > 0:
        current_weights = {k: round(v / total, 4) for k, v in current_weights.items()}

    router["scoring_weights"] = current_weights
    router["updated"] = datetime.now().strftime("%Y-%m-%d")

    ROUTER_PATH.write_text(json.dumps(router, indent=2), encoding="utf-8")

    return {"updated": True, "new_weights": current_weights}


def get_daily_learning_report() -> dict:
    """Generate daily learning report for night operations."""
    memory = _load_memory()
    today = datetime.now().strftime("%Y-%m-%d")

    today_campaigns = [
        c for c in memory.get("campaigns", [])
        if c.get("timestamp", "").startswith(today)
    ]

    brand_perf = get_brand_performance_summary()
    insights = get_learning_insights()

    return {
        "report_date": today,
        "campaigns_today": len(today_campaigns),
        "total_campaigns": len(memory.get("campaigns", [])),
        "brand_performance": brand_perf,
        "top_hooks": get_winning_hooks(limit=5),
        "top_titles": get_winning_titles(limit=5),
        "best_posting_times": get_best_posting_times(),
        "insights": insights,
    }
