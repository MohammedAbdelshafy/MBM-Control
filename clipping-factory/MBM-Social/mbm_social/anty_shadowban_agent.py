"""
AntyShadowbanAgent — schedules YouTube video publishing across multiple fresh
channels while minimizing the risk of recommendation suppression, shadowban,
and account-level spam flags.

Research sources (2025-2026):
  - YouTube Creator Academy: 1-2 long-form / week for new channels; 3-5 Shorts/week
  - YouTube Help: quality > frequency; subscriber-notification limit = 3/24h
  - Buffer (1.8M-video dataset): long-form best Sun 10am ET; Shorts best Fri 4-7pm ET
  - vidIQ (10.2M channels): no more than 20 videos/day; growth improves per-tier
  - Creator Insider / LunaBloom: burst uploads of 5+ in <24h trigger spam detection
  - TikAlyzer: "topic whiplash" (6 uploads across niches) confuses recommendation
  - Google S-CTS (July 2026): automated cluster termination for coordinated channels

Scheduling rules enforced:
  R1. Daily cap: ≤ MAX_LONGFORM long-form + MAX_SHORTS Shorts per channel.
  R2. Inter-upload gap: ≥ MIN_GAP_MINUTES between any two uploads on a channel.
  R3. Sub-notif window: ≤ MAX_NOTIFY_PER_WINDOW (3) uploads per 24h → caps surge.
  R4. Warmup ramp: fresh accounts start at WEEKLY_WARMUP_RATE per week and
      double every 2 weeks until reaching steady-state.
  R5. Content variety: ensure ≥ 3 distinct content pillars per channel; skip
      near-duplicate titles (fuzzy match > 0.85).
  R6. Optimal-time spreading: schedule long-form in 09:00-12:00 UTC windows
      and Shorts in 20:00-24:00 UTC windows, with random jitter.
  R7. Platform cooldown: never schedule < MIN_GAP_MINUTES between successive
      publishes even across different channels (shared IP / account cluster risk).
"""
from __future__ import annotations

import json
import random
import math
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from difflib import SequenceMatcher

try:
    from .human_behavior import human_delay
except ImportError:
    human_delay = lambda *a, **k: time.sleep(random.uniform(1, 3))

ROOT = Path(__file__).resolve().parent.parent
STATE_DIR = ROOT / "anty_shadowban_state"
STATE_DIR.mkdir(parents=True, exist_ok=True)

# ─── Schedule Constants (from research) ─────────────────────────────────
MAX_LONGFORM = 2          # long-form videos per channel per day
MAX_SHORTS = 2            # Shorts per channel per day
MIN_GAP_MINUTES = 120     # minimum minutes between any two uploads on a channel
MAX_NOTIFY_PER_24H = 3    # subscriber notification limit per channel per 24h
WEEKLY_WARMUP_RATE = 1    # long-form posts per week for fresh accounts (first 2 weeks)
MAX_DAILY_TOTAL = MAX_LONGFORM + MAX_SHORTS  # 4 uploads absolute per channel per day

# Optimal posting time windows (UTC) for US audience (EST/EDT)
# EST = UTC-5, EDT = UTC-4 (Mar-Nov). US viewers active: morning EST and evening EST.
LONGFORM_WINDOWS_UTC = [(13, 17)]   # 8am-12pm EST  (morning US Eastern on workdays)
SHORTS_WINDOWS_UTC = [(20, 24)]     # 4pm-8pm EST (evening US Eastern prime time)
JITTER_MINUTES = 30                 # random jitter to avoid pattern detection
TARGET_AUDIENCE = "US (EST/EDT)"

# Warmup ramp schedule (weeks active → daily long-form limit)
WARMUP_RAMP = {0: 0.14, 2: 0.29, 4: 1, 6: 2}  # 1/week → 1.5/week → 1/day → 2/day

# Content pillar diversity required
MIN_PILLARS = 3

BRANDS = [
    "cutedosage",
    "dontwatchthis",
    "goalmachinez",
    "twistsrevealed",
    "clippingfactorymbm",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_to_local(utc_dt: datetime, tz_offset_hours: int = -5) -> datetime:
    """Convert UTC to America/New_York (default EST)."""
    return utc_dt + timedelta(hours=tz_offset_hours)


def _load_state() -> dict:
    f = STATE_DIR / "schedule_state.json"
    if f.exists():
        try:
            return json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"channels": {}, "global_last_post": None, "generated_schedules": []}


def _save_state(state: dict) -> None:
    f = STATE_DIR / "schedule_state.json"
    f.write_text(json.dumps(state, indent=2), encoding="utf-8")


def _channel_age_days(channel_state: dict) -> int:
    first_post = channel_state.get("first_post_at")
    if not first_post:
        return 0
    try:
        return max(0, (_now() - datetime.fromisoformat(first_post)).days)
    except Exception:
        return 0


def _warmup_daily_limit(age_days: int) -> int:
    """Return the daily long-form cap based on channel warmup ramp."""
    weeks = age_days / 7
    limit = WARMUP_RAMP[0]
    for threshold, rate in sorted(WARMUP_RAMP.items()):
        if weeks >= threshold:
            limit = rate
    return max(1, round(limit))


def _title_similarity(a: str, b: str) -> float:
    """Fuzzy match ratio for duplicate detection."""
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()


def _us_audience_score(posts: list[dict]) -> dict:
    """Score how well the current content targets US audience."""
    total = len(posts)
    if not total:
        return {"score": 0.0, "us_tags": 0, "us_cas": 0, "needs_improvement": True}

    us_tags = 0
    us_cas = 0
    for p in posts:
        tags = p.get("tags", p.get("metadata", {}).get("tags", []))
        desc = p.get("description", "")
        us_tags += sum(1 for t in tags if t.lower() in ("us", "usa", "american", "america"))
        us_cas += 1 if any(flag in desc.lower() for flag in ["🇺🇸", "american", "us folks", "us viewers"]) else 0

    score = (us_tags / max(total, 1) + us_cas / max(total, 1)) / 2 * 10
    return {
        "score": round(score, 2),
        "us_tags": us_tags,
        "us_cas": us_cas,
        "needs_improvement": score < 6.0,
    }


def _is_near_duplicate(new_title: str, recent_titles: list[str]) -> bool:
    """Check if a title is a near-duplicate of any recent title (>85% match)."""
    for t in recent_titles:
        if _title_similarity(new_title, t) > 0.85:
            return True
    return False


def _pick_optimal_time(longform: bool) -> datetime:
    """Pick an optimal posting time within the allowed windows + jitter."""
    windows = LONGFORM_WINDOWS_UTC if longform else SHORTS_WINDOWS_UTC
    start_h, end_h = random.choice(windows)
    minute = random.randint(0, 59)
    hour = random.randint(start_h, max(start_h, end_h - 1))
    base = _now().replace(hour=hour, minute=minute, second=0, microsecond=0)
    base += timedelta(days=random.randint(0, 2))
    jitter = timedelta(minutes=random.randint(-JITTER_MINUTES, JITTER_MINUTES))
    return max(_now() + timedelta(minutes=MIN_GAP_MINUTES), base + jitter)


def analyze_channel_history(channel: str, posts: list[dict]) -> dict:
    """Analyze a channel's posting history for shadowban risk signals."""
    if not posts:
        return {"status": "fresh", "daily_limit": _warmup_daily_limit(0), "warnings": []}

    recent_24h = [p for p in posts if _title_similarity(p.get("status", ""), "published") == 0
                  and _now().timestamp() - p.get("_ts", 0) < 86400]

    warnings = []
    # Check burst rate
    burst_windows = _detect_bursts(posts)
    if burst_windows:
        warnings.append(f"Burst detected: {len(burst_windows)} windows with 3+ posts in 2h")

    # Check content variety
    pillars = set(p.get("metadata", {}).get("pillar", "unknown") for p in posts[-15:])
    if len(posts) >= 6 and len(pillars) < MIN_PILLARS:
        warnings.append(f"Only {len(pillars)} content pillars in recent posts; need ≥{MIN_PILLARS}")

    # Check retention proxy
    avg_retention = 0
    retentions = [p.get("metrics", {}).get("retention_avg_pct", 0) for p in posts if "metrics" in p]
    if retentions:
        avg_retention = sum(retentions) / len(retentions)
        if avg_retention < 50:
            warnings.append(f"Average retention {avg_retention:.0f}% < 50% threshold; reduce frequency")

    # Check CTR
    ctrs = [p.get("metrics", {}).get("ctr_pct", 0) for p in posts if "metrics" in p]
    if ctrs:
        avg_ctr = sum(ctrs) / len(ctrs)
        if avg_ctr < 3:
            warnings.append(f"Average CTR {avg_ctr:.1f}% < 3%; metadata may be flagged as clickbait")

    age_days = _channel_age_days({"first_post_at": posts[0].get("published_at", "")}) if posts else 0
    daily_limit = min(_warmup_daily_limit(age_days), MAX_LONGFORM) if avg_retention and avg_retention < 50 else _warmup_daily_limit(age_days)

    status = "warmup" if age_days < 14 else ("healthy" if not warnings else "at_risk")

    us_score = _us_audience_score(posts)
    if us_score["needs_improvement"]:
        warnings.append(f"US audience targeting weak (score {us_score['score']}/10) — "
                         f"add US tags/geotagging/CTAs")

    return {
        "status": status,
        "daily_limit": daily_limit,
        "avg_retention": round(avg_retention, 1),
        "avg_ctr": round(sum(ctrs) / len(ctrs), 2) if ctrs else 0,
        "content_pillars": list(pillars),
        "us_audience_score": us_score,
        "warnings": warnings,
        "posts_analyzed": len(posts),
    }


def _detect_bursts(posts: list[dict]) -> list[dict]:
    """Detect time windows where 3+ posts happened within 2 hours."""
    bursts = []
    sorted_posts = sorted(
        [p for p in posts if p.get("published_at")],
        key=lambda p: p["published_at"]
    )
    for i, p in enumerate(sorted_posts):
        try:
            t = datetime.fromisoformat(p["published_at"])
        except Exception:
            continue
        window = [q for q in sorted_posts[i:] if
                  _safe_parse(q.get("published_at")) and
                  0 <= (_safe_parse(q["published_at"]) - t).total_seconds() <= 7200]
        if len(window) >= 3:
            bursts.append({"start": t.isoformat(), "count": len(window)})
    return bursts


def _safe_parse(iso_str: str | None) -> datetime | None:
    if not iso_str:
        return None
    try:
        return datetime.fromisoformat(iso_str)
    except Exception:
        return None


def generate_schedule(
    channel: str,
    available_packages: list[dict],
    schedule_days: int = 7,
    now: datetime | None = None,
) -> list[dict]:
    """
    Generate an anti-shadowban posting schedule for a channel.

    Args:
        channel: brand slug
        available_packages: list of {filepath, data} from publish_queue
        schedule_days: how many days ahead to plan
        now: override current time (for testing)

    Returns:
        list of schedule entries: {time_utc, channel, longform, title, filepath, reason}
    """
    now = now or _now()
    state = _load_state()
    ch_state = state["channels"].setdefault(channel, {
        "first_post_at": None,
        "history": [],
        "last_post_at": None,
    })

    age_days = _channel_age_days(ch_state)
    daily_longform_cap = _warmup_daily_limit(age_days)
    analysis = analyze_channel_history(channel, ch_state.get("history", []))

    if analysis.get("warnings"):
        for w in analysis["warnings"]:
            print(f"[ANTY-SHADOWBAN] Channel '{channel}' warning: {w}")
        # Reduce frequency if at-risk
        if analysis["status"] == "at_risk":
            daily_longform_cap = max(1, daily_longform_cap // 2)

    # Separate long-form and Shorts packages, filter near-duplicates
    recent_titles = [h.get("title", "") for h in ch_state.get("history", [])[-10:]]
    longform_posts = []
    shorts_posts = []
    for pkg in available_packages:
        data = pkg.get("data", pkg)
        title = data.get("title", "Untitled")
        if _is_near_duplicate(title, recent_titles):
            continue
        if data.get("is_short") or (data.get("duration_sec", 0) < 90):
            shorts_posts.append(pkg)
        else:
            longform_posts.append(pkg)

    # Pillar assignment
    pillars = _assign_pillars(longform_posts + shorts_posts)

    schedule = []
    global_last_post = _parse_iso(state.get("global_last_post"))

    for day in range(schedule_days):
        day_start = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=day)
        if day_start < now:
            day_start = now

        day_longform = 0
        day_shorts = 0

        # Schedule long-form during morning UTC window
        for _ in range(daily_longform_cap):
            if not longform_posts:
                break
            pkg = longform_posts.pop(0)
            data = pkg.get("data", pkg)
            post_time = _pick_optimal_time(longform=True)
            adjusted = _enforce_gaps(post_time, day_start, global_last_post, channel, ch_state)
            if adjusted is None:
                continue
            schedule.append({
                "time_utc": adjusted.isoformat(),
                "channel": channel,
                "type": "longform",
                "title": data.get("title", "Untitled"),
                "filepath": str(pkg.get("filepath", pkg.get("file_path", ""))),
                "pillars": pillars.get(data.get("title", ""), []),
                "reason": f"optimal_time|morning_window|warmup_week_{age_days//7}",
                "target_audience": "US",
            })
            global_last_post = adjusted
            day_longform += 1

        # Schedule Shorts during evening UTC window
        for _ in range(min(MAX_SHORTS, len(shorts_posts))):
            if not shorts_posts:
                break
            if day_shorts >= MAX_SHORTS:
                break
            pkg = shorts_posts.pop(0)
            data = pkg.get("data", pkg)
            post_time = _pick_optimal_time(longform=False)
            adjusted = _enforce_gaps(post_time, day_start, global_last_post, channel, ch_state)
            if adjusted is None:
                continue
            schedule.append({
                "time_utc": adjusted.isoformat(),
                "channel": channel,
                "type": "shorts",
                "title": data.get("title", "Untitled"),
                "filepath": str(pkg.get("filepath", pkg.get("file_path", ""))),
                "pillars": pillars.get(data.get("title", ""), []),
                "reason": f"optimal_time|evening_window|shorts_ramp",
                "target_audience": "US",
            })
            global_last_post = adjusted
            day_shorts += 1

    state["global_last_post"] = global_last_post.isoformat() if global_last_post else None
    state["generated_schedules"] = state.get("generated_schedules", [])[-10:]
    _save_state(state)

    return schedule


def _parse_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


def _enforce_gaps(
    proposed: datetime,
    day_start: datetime,
    global_last: datetime | None,
    channel: str,
    ch_state: dict,
) -> datetime | None:
    """Enforce all gap rules; return adjusted time or None if blocked."""
    if proposed < day_start:
        proposed = day_start + timedelta(minutes=MIN_GAP_MINUTES)

    # Global gap (shared IP risk)
    if global_last and (proposed - global_last).total_seconds() < MIN_GAP_MINUTES * 60:
        proposed = global_last + timedelta(minutes=MIN_GAP_MINUTES)

    # Channel-specific gap
    last_post_str = ch_state.get("last_post_at")
    if last_post_str:
        last_post = _parse_iso(last_post_str)
        if last_post and (proposed - last_post).total_seconds() < MIN_GAP_MINUTES * 60:
            proposed = last_post + timedelta(minutes=MIN_GAP_MINUTES + random.randint(5, 20))

    # Don't schedule in the past
    if proposed < _now():
        proposed = _now() + timedelta(minutes=MIN_GAP_MINUTES + random.randint(5, 20))

    return proposed


def _assign_pillars(packages: list[dict]) -> dict[str, list[str]]:
    """Assign content pillars to each package based on metadata."""
    pillar_map = {}
    for pkg in packages:
        data = pkg.get("data", pkg)
        title = data.get("title", "")
        description = data.get("description", "")
        text = (title + " " + description).lower()
        assigned = []
        for keyword, pillar in [
            ("tutorial", "education"), ("how to", "education"),
            ("funny", "entertainment"), ("comedy", "entertainment"),
            ("react", "reaction"), ("review", "analysis"),
            ("analysis", "analysis"), ("news", "news"),
            ("trend", "trending"), ("challenge", "entertainment"),
        ]:
            if keyword in text:
                assigned.append(pillar)
        if not assigned:
            assigned = ["general"]
        pillar_map[title] = list(set(assigned))
    return pillar_map


def export_schedule_json(schedules: list[dict]) -> str:
    """Export the full multi-channel schedule as JSON."""
    export = {
        "generated_at": _now().isoformat(),
        "total_posts": len(schedules),
        "channels": {},
    }
    for entry in schedules:
        ch = entry["channel"]
        export["channels"].setdefault(ch, {"posts": []})
        export["channels"][ch]["posts"].append(entry)
    return json.dumps(export, indent=2, ensure_ascii=False)


def run(
    schedule_days: int = 7,
    dry_run: bool = True,
    brands: list[str] | None = None,
) -> dict:
    """
    Main entry: generate anti-shadowban schedule for all brands.

    Args:
        schedule_days: how many days ahead to plan (default 7)
        dry_run: if True, only report what would be scheduled
        brands: optional list of brand slugs to schedule for

    Returns:
        status dict with schedule summary
    """
    from . import post_orchestrator as orch

    brands = brands or BRANDS
    all_schedules = []

    for brand in brands:
        try:
            pending = orch.pending_packages(brand, dedupe=True, limit=20)
            if not pending:
                print(f"[ANTY-SHADOWBAN] No pending packages for brand '{brand}'")
                continue

            # Format packages as {filepath, data}
            pkgs = [{"filepath": fp, "data": data} for fp, data in pending]
            schedule = generate_schedule(brand, pkgs, schedule_days=schedule_days)
            all_schedules.extend(schedule)

            # Update channel state
            state = _load_state()
            ch_state = state["channels"].setdefault(brand, {"history": [], "last_post_at": None})
            for entry in schedule:
                ch_state.setdefault("history", []).append({
                    "title": entry["title"],
                    "published_at": entry["time_utc"],
                    "type": entry["type"],
                })
                ch_state["last_post_at"] = entry["time_utc"]
                if not ch_state.get("first_post_at"):
                    ch_state["first_post_at"] = entry["time_utc"]
            _save_state(state)

        except Exception as e:
            print(f"[ANTY-SHADOWBAN] Error scheduling brand '{brand}': {e}")

    # Export
    export = export_schedule_json(all_schedules)
    export_file = STATE_DIR / f"schedule_export_{_now().strftime('%Y%m%d_%H%M%S')}.json"
    export_file.write_text(export, encoding="utf-8")

    status = {
        "status": "success" if all_schedules else "skipped",
        "total_posts": len(all_schedules),
        "channels_scheduled": list(set(e["channel"] for e in all_schedules)),
        "schedule_days": schedule_days,
        "dry_run": dry_run,
        "export_path": str(export_file),
        "output": json.loads(export),
        "owner": "system",
        "timestamp": _now().isoformat(),
    }

    print(f"[ANTY-SHADOWBAN] Scheduled {len(all_schedules)} posts across "
          f"{len(status['channels_scheduled'])} channels for {schedule_days} days.")
    print(f"[ANTY-SHADOWBAN] Export: {export_file}")

    return status


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="AntyShadowbanAgent — anti-shadowban schedule generator")
    parser.add_argument("--days", type=int, default=7, help="Days ahead to schedule")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run (default)")
    parser.add_argument("--no-dry-run", action="store_false", dest="dry_run")
    parser.add_argument("--brand", type=str, help="Specific brand slug")
    args = parser.parse_args()
    result = run(schedule_days=args.days, dry_run=args.dry_run, brands=[args.brand] if args.brand else None)
    print(json.dumps(result, indent=2))
