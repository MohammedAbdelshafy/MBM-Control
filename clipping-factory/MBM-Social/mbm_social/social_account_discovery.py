"""
social_account_discovery — Daily content discovery + package generation engine.

Feeds the AnTyShadowbanAgent scheduler with fresh, varied content packages.
Generates up to 100 video packages per day per channel (long-form + Shorts),
distributed across 3-5 content pillars to maintain diversity and avoid
recommendation suppression.

The pipeline works in three stages:
  1. Discover trending topics / clips for each brand (sources.yaml)
  2. Generate 100 short-form clips + 100 long-form videos per brand
  3. Queue them into publish_queue/ as draft packages with metadata

Usage:
   python -m mbm_social.social_account_discovery                  # generate today's batch
   python -m mbm_social.social_account_discovery --brand cute      # one brand only
   python -m mbm_social.social_account_discovery --count 100       # override count
   python -m mbm_social.social_account_discovery --dry-run         # don't write queue
"""
from __future__ import annotations

import argparse
import json
import random
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    from .human_behavior import human_delay
except ImportError:
    import time as _t
    human_delay = lambda *a, **k: _t.sleep(random.uniform(0.5, 2))

ROOT = Path(__file__).resolve().parent.parent
QUEUE_DIR = ROOT / "publish_queue"
QUEUE_DIR.mkdir(parents=True, exist_ok=True)

# Daily content quotas per brand
LONGFORM_PER_CHANNEL = 100
SHORTS_PER_CHANNEL = 100

# Content pillars (must be >= 3 per AnTyShadowbanAgent requirements)
PIllAR = "US_focused"
PILLARS = ["entertainment", "education", "analysis", "trending", "news_reaction"]

# US-specific topics (American audience targeting)
TOPICS = [
    "AI Art", "Short-Form Video", "Creator Economy", "YouTube Shorts",
    "TikTok Viral", "Meme Culture", "Viral Challenges", "Algorithm Secrets",
    "Content Marketing", "Niche Channels", "Algorithm Updates", "Monetization",
    "Subscriber Growth", "Video Editing", "Thumbnail Design", "Trend Hijacking",
    "Community Posts", "Live Streaming", "Demonetization", "Copyright Issues",
]

# US-specific hashtags and cultural references
US_HASHTAGS = ["#Shorts", "#fyp", "#usa", "#trending", "#viral", "#creator",
               "#youtube", "#shorts", "#content", "#ai", "#tech", "#funny"]

# Title templates per pillar (rotating, never word-swap duplicates)
TITLE_TEMPLATES = {
    "entertainment": [
        "This {topic} Trend Is Absolutely Unhinged 😱",
        "We Tried {topic} So You Don't Have To",
        "The {topic} Moment That Broke the Internet",
        "{topic}: The Lost Media They Didn't Want You To See",
        "Why {topic} Got BANNED From YouTube",
        "Our {topic} Experiment Went Horribly Wrong",
        "The Dark Truth Behind {topic}",
        "{topic} Compilation That Will Haunt You",
    ],
    "education": [
        "How {topic} Actually Works (Explained)",
        "The Science Behind {topic}: Full Breakdown",
        "Everything You Need To Know About {topic}",
        "Beginner's Guide To Understanding {topic}",
        "Why {topic} Matters More Than You Think",
        "The History Of {topic} You Never Learned",
        "How {topic} Changes Everything",
    ],
    "analysis": [
        "Analyzing {topic}: The Numbers Don't Lie",
        "The {topic} Market Shift No One Saw Coming",
        "Breaking Down The {topic} Data",
        "Why The Experts Got {topic} Wrong",
        "The Real Story Behind {topic}",
        "{topic} By The Numbers: A Deep Dive",
    ],
    "trending": [
        "{topic} Is Trending Right Now — Here's Why",
        "Why Everyone Is Obsessed With {topic}",
        "The {topic} Trend Taking Over {year}",
        "This {topic} Hack Went Viral Overnight",
        "How {topic} Became The Biggest Meme",
        "{topic} Explained In 60 Seconds",
    ],
    "news_reaction": [
        "Our Reaction To The {topic} News",
        "Breaking: {topic} Just Changed Everything",
        "Live Reaction To {topic} Announcement",
        "What The {topic} News Means For You",
        "The {topic} Update Nobody Asked For",
        "Our Honest Take On {topic} Today",
    ],
}

TOPICS = [
    "AI Art", "Short-Form Video", "Creator Economy", "YouTube Shorts",
    "TikTok Viral", "Meme Culture", "Viral Challenges", "Algorithm Secrets",
    "Content Marketing", "Niche Channels", "Algorithm Updates", "Monetization",
    "Subscriber Growth", "Video Editing", "Thumbnail Design", "Trend Hijacking",
    "Community Posts", "Live Streaming", "Demonetization", "Copyright Issues",
]

HASHTAGS = US_HASHTAGS

# US-specific engagement boosters — calls-to-action encouraging American audience interaction
US_ENGAGEMENT_CTAS = [
    "Drop a 🇺🇸 if you're watching from the US!",
    "Comment below: US or bust! 👇",
    "American viewers — what do you think about this?",
    "Tag an American friend who needs to see this 🇺🇸",
    "US folks, how does this compare to your experience?",
    "Drop your state in the comments if you're in the USA!",
    "American creators — save this for later 🔖",
    "US audience — what would you do differently?",
]

# US-centric description suffixes
US_DESCRIPTION_SUFFIXES = [
    "\n\n🔔 Subscribe for daily US-focused insights!\n\n#America #US #USA #UnitedStates",
    "\n\n📍 Targeting US viewers — share with your American friends!\n\n#America #USATrends #USA",
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_title(pillar: str, topic: str) -> str:
    """Generate a unique title from the template pool."""
    template = random.choice(TITLE_TEMPLATES.get(pillar, TITLE_TEMPLATES["entertainment"]))
    year = datetime.now().year
    return template.format(topic=topic, year=year)


def _generate_description(pillar: str, topic: str, is_short: bool = False) -> str:
    """Generate a content-rich description targeting US audience with engagement CTAs."""
    base = f"Exploring the world of {topic} through the lens of {pillar} analysis."
    if is_short:
        base += " This is a Shorts-style quick take with maximum impact."
    else:
        base += " Full breakdown, deep insights, and actionable takeaways."

    # US-specific engagement CTA
    cta = random.choice(US_ENGAGEMENT_CTAS)
    suffix = random.choice(US_DESCRIPTION_SUFFIXES)

    tags = random.sample(HASHTAGS, k=min(5, len(HASHTAGS)))
    tag_str = " ".join(tags)
    cta_str = f"\n\n{cta}"

    desc = f"{base}{cta_str}\n{tag_str}{suffix}"
    return (desc + "\n\n#Shorts") if is_short else desc


def _generate_filepath(brand: str, index: int, is_short: bool = False) -> str:
    """Generate a deterministic clip file path."""
    suffix = "short" if is_short else "long"
    safe_brand = brand.replace(" ", "").lower()
    return f"clip_{safe_brand}_{suffix}_{index:04d}.mp4"


def _extract_tags(title: str, pillar: str) -> list[str]:
    """Extract searchable tags targeting US audience from title and pillar."""
    import re
    words = re.findall(r'\b[A-Za-z]{3,}\b', title.lower())
    tags = [w for w in words if w not in ("the", "and", "for", "with", "this", "that", "have", "will")]
    tags = list(dict.fromkeys(tags))[:5]  # dedupe, limit
    # Always include US-targeted and pillar tags
    us_tags = ["us", "usa", "american", "america"]
    pillar_tags = {
        "entertainment": ["viral", "funny"],
        "education": ["tutorial", "learn"],
        "analysis": ["data", "analysis"],
        "trending": ["trending", "fyp"],
        "news_reaction": ["news", "trending"],
    }
    tags.extend(us_tags)
    tags.extend(pillar_tags.get(pillar, ["content"]))
    return list(dict.fromkeys(tags))  # final dedupe


def generate_brand_content(brand: str, count: int = None) -> list[dict]:
    """
    Generate content packages for a brand.

    Returns list of package dicts ready for publish_queue.
    Distributes across LONGFORM_PER_CHANNEL long-form + SHORTS_PER_CHANNEL shorts.
    """
    long_count = min(count // 2 if count else LONGFORM_PER_CHANNEL, LONGFORM_PER_CHANNEL)
    short_count = min(count - long_count if count else SHORTS_PER_CHANNEL, SHORTS_PER_CHANNEL)
    if count and long_count + short_count < count:
        short_count = count - long_count

    packages = []

    for i in range(long_count):
        pillar = PILLARS[i % len(PILLARS)]
        topic = TOPICS[random.randint(0, len(TOPICS) - 1)]
        title = _generate_title(pillar, topic)
        package = {
            "id": str(uuid.uuid4()),
            "brand": brand,
            "title": title,
            "description": _generate_description(pillar, topic, is_short=False),
            "video_path": str(QUEUE_DIR.parent / "clips" / _generate_filepath(brand, i, is_short=False)),
            "is_short": False,
            "metadata": {
                "pillar": pillar,
                "topic": topic,
                "duration_sec": random.randint(300, 600),
                "target_audience": "US",
                "geotag": "US",
                "language": "en-US",
            },
            "tags": _extract_tags(title, pillar),
            "status": "draft",
            "scheduled_for": None,
            "created_at": _now().isoformat(),
            "metrics": {},
        }
        packages.append(package)
        human_delay(0.1, 0.5)

    for i in range(short_count):
        pillar = PILLARS[i % len(PILLARS)]
        topic = TOPICS[random.randint(0, len(TOPICS) - 1)]
        title = _generate_title(pillar, topic)
        package = {
            "id": str(uuid.uuid4()),
            "brand": brand,
            "title": title,
            "description": _generate_description(pillar, topic, is_short=True),
            "video_path": str(QUEUE_DIR.parent / "clips" / _generate_filepath(brand, i, is_short=True)),
            "is_short": True,
            "metadata": {
                "pillar": pillar,
                "topic": topic,
                "duration_sec": random.randint(15, 60),
                "target_audience": "US",
                "geotag": "US",
                "language": "en-US",
            },
            "tags": _extract_tags(title, pillar),
            "status": "draft",
            "scheduled_for": None,
            "created_at": _now().isoformat(),
            "metrics": {},
        }
        packages.append(package)
        human_delay(0.1, 0.3)

    return packages


def write_packages_to_queue(packages: list[dict]) -> int:
    """Write packages to publish_queue/ as JSON files. Returns count written."""
    written = 0
    for pkg in packages:
        filepath = QUEUE_DIR / f"{pkg['id']}.json"
        if not filepath.exists():
            filepath.write_text(json.dumps(pkg, indent=2), encoding="utf-8")
            written += 1
    return written


def discover_trending_topics(brand: str) -> list[str]:
    """
    Discover trending topics from brand's sources.yaml.
    Falls back to TOPIC pool if no sources config exists.
    """
    sources_path = ROOT / "Brands" / brand / "sources.yaml"
    if not sources_path.exists():
        return random.sample(TOPICS, k=min(5, len(TOPICS)))

    try:
        import yaml
        with open(sources_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return list(data.get("trending_topics", []))
    except Exception:
        return random.sample(TOPICS, k=min(5, len(TOPICS)))


def run(
    brand: str | None = None,
    count: int = None,
    dry_run: bool = True,
) -> dict:
    """
    Main entry: generate content packages and queue them.

    Args:
        brand: specific brand slug; if None, process all BRANDS
        count: override total package count per brand
        dry_run: if True, don't write to queue

    Returns:
        status dict
    """
    from mbm_social import brand_config as bc

    if brand:
        brands = [brand]
    else:
        try:
            brands = bc.list_brands()
        except Exception:
            brands = ["cutedosage", "dontwatchthis", "goalmachinez", "twistsrevealed", "clippingfactorymbm"]

    total_generated = 0
    results = {}

    for br in brands:
        safe_brand = br.get("slug", br) if isinstance(br, dict) else br
        actual_count = count or (LONGFORM_PER_CHANNEL + SHORTS_PER_CHANNEL)
        packages = generate_brand_content(safe_brand, count=actual_count)
        written = write_packages_to_queue(packages) if not dry_run else len(packages)
        total_generated += written
        results[safe_brand] = {
            "generated": len(packages),
            "written": written,
            "longform": sum(1 for p in packages if not p["is_short"]),
            "shorts": sum(1 for p in packages if p["is_short"]),
        }
        print(f"[SOCIAL-DISCOVERY] Brand '{safe_brand}': {written} packages "
              f"({results[safe_brand]['longform']} long-form, {results[safe_brand]['shorts']} Shorts)")
        human_delay(0.5, 2)

    status = {
        "status": "success" if total_generated > 0 else "skipped",
        "total_packages": total_generated,
        "brands": results,
        "queue_dir": str(QUEUE_DIR),
        "owner": "system",
        "timestamp": _now().isoformat(),
    }

    print(f"[SOCIAL-DISCOVERY] Total: {total_generated} packages queued.")
    return status


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Social Account Discovery — content generator")
    parser.add_argument("--brand", type=str, help="Specific brand slug")
    parser.add_argument("--count", type=int, default=None, help="Packages per brand")
    parser.add_argument("--dry-run", action="store_true", default=True, help="Dry run (default)")
    parser.add_argument("--no-dry-run", action="store_false", dest="dry_run")
    args = parser.parse_args()
    result = run(brand=args.brand, count=args.count, dry_run=args.dry_run)
    print(json.dumps(result, indent=2))
