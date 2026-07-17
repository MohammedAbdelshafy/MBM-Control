"""
MBM-Social brand-config generator.

This is the ONLY place brand defaults live. Adding a new channel later
requires: add one entry to BRANDS below, rerun this script, commit.
No framework code changes needed.

Run:
    cd clipping-factory/MBM-Social
    python tools/gen_brand_configs.py
"""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parent.parent
BRANDS_DIR = ROOT / "Brands"

# Master control account (single Gmail owns every channel / brand account).
MASTER_EMAIL = "abdelshafyclapps@gmail.com"

BRANDS = [
    {
        "slug": "dontwatchthis",
        "display": "Don't Watch This",
        "handle": "@DONTWATCHTHIS1",
        "youtube_channel": "UC_DONTWATCHTHIS1",
        "theme": "dark stories, chilling truths, mystery, suspense",
        "voice": "suspense-heavy, dark, mysterious",
        "title_style": "short, punchy, mystery-forward",
        "caption_style": "mystery-forward, curiosity gaps, no spoilers",
        "hook_style": "suspense-heavy",
        "visual_style": "dark visuals, high contrast, desaturated",
        "emoji_policy": "minimal",
        "primary_category": "Entertainment",
        "keywords": ["mystery", "suspense", "dark story", "true crime lite", "chilling"],
        "posting": {"cadence": "daily", "windows": ["20:00", "22:00"], "timezone": "America/New_York"},
        "kpis": {"target_views_30d": 500000, "target_ctr": 0.06, "target_avg_view_pct": 0.45,
                  "target_subs_per_post": 300, "priority": "watch_time"},
        "thumb_rules": "Dark, desaturated background. One shocked/ominous face or silhouette. "
                       "Max 3 words, white bold, slight red accent. No bright colors.",
        "title_rules": "3-7 words. Lead with the unsettling fact. No clickbait that breaks the mystery. "
                       "Question or bold statement.",
        "caption_rules": "Open with a hook line. 1-2 sentences, curiosity gap, no spoilers. "
                         "End with 3-5 niche hashtags.",
    },
    {
        "slug": "goalmachinez",
        "display": "Goal Machinez",
        "handle": "@Goalmachinez",
        "youtube_channel": "UC_Goalmachinez",
        "theme": "football / soccer / sports highlights and commentary",
        "voice": "sports-first, energetic, fan-native",
        "title_style": "highlight-driven, fast, energetic",
        "caption_style": "fast pacing, highlight-driven, emoji if it lifts performance",
        "hook_style": "sports-first",
        "visual_style": "fast cuts, stadium energy, bright pitch colors",
        "emoji_policy": "allowed-if-performance",
        "primary_category": "Sports",
        "keywords": ["football", "soccer", "goal", "highlight", "match", "tactic"],
        "posting": {"cadence": "3x daily", "windows": ["12:00", "18:00", "22:30"], "timezone": "Europe/London"},
        "kpis": {"target_views_30d": 800000, "target_ctr": 0.07, "target_avg_view_pct": 0.50,
                  "target_subs_per_post": 400, "priority": "views"},
        "thumb_rules": "Bright, high-energy. Player mid-action or celebration. Bold team colors. "
                       "2-4 words, heavy italic. Optional flame/ball emoji.",
        "title_rules": "Lead with the moment: 'INSANE goal', 'Last-minute winner'. 4-8 words. "
                       "Use team/player names. Emoji allowed if it fits.",
        "caption_rules": "Lead with the play. 1-2 lines, energetic. Hashtags with leagues/teams/players.",
    },
    {
        "slug": "cutedosage",
        "display": "Cute Dosage",
        "handle": "@CuteDosage",
        "youtube_channel": "UC_CuteDosage",
        "theme": "cute, wholesome, family, pet, baby-style content",
        "voice": "warm, wholesome, family-safe",
        "title_style": "friendly, soft, heartwarming",
        "caption_style": "soft captions, warm, family-safe",
        "hook_style": "warm",
        "visual_style": "clean, bright, soft pastel thumbnails",
        "emoji_policy": "soft-allowed",
        "primary_category": "People & Blogs",
        "keywords": ["cute", "wholesome", "pets", "babies", "family", "feel good"],
        "posting": {"cadence": "2x daily", "windows": ["09:00", "17:00"], "timezone": "America/Chicago"},
        "kpis": {"target_views_30d": 600000, "target_ctr": 0.08, "target_avg_view_pct": 0.55,
                  "target_subs_per_post": 500, "priority": "likes"},
        "thumb_rules": "Clean bright pastel background. Big soft smile / cute animal. Rounded text, "
                       "friendly font. No harsh edges.",
        "title_rules": "Warm and friendly. 3-6 words. 'You won't believe this puppy...'. Soft tone.",
        "caption_rules": "Warm open. 1-2 sentences, wholesome. Family-safe hashtags only.",
    },
    {
        "slug": "clippingfactorymbm",
        "display": "ClippingFactoryMBM",
        "handle": "@ClippingFactoryMBM",
        "youtube_channel": "UC_ClippingFactoryMBM",
        "theme": "MBM operations, clipping factory, build-in-public, internal brand",
        "voice": "behind-the-scenes, proof-of-work, technical",
        "title_style": "build-in-public, case-study, how-we-did-it",
        "caption_style": "proof-of-work, pipeline demos, case studies",
        "hook_style": "curiosity / proof",
        "visual_style": "screen captures, pipeline diagrams, real metrics on screen",
        "emoji_policy": "minimal",
        "primary_category": "Science & Technology",
        "keywords": ["clipping", "automation", "AI", "build in public", "passive income"],
        "posting": {"cadence": "weekly", "windows": ["15:00"], "timezone": "America/New_York"},
        "kpis": {"target_views_30d": 150000, "target_ctr": 0.05, "target_avg_view_pct": 0.40,
                  "target_subs_per_post": 150, "priority": " authority / leads"},
        "thumb_rules": "Real metric or screenshot. Clean, technical. Brand color accent. "
                       "Text = the result or 'how we did it'.",
        "title_rules": "How-we / case-study framing. 'We auto-posted 30 clips with local LLMs'. 5-9 words.",
        "caption_rules": "Proof-of-work open. Link to methodology. Technical but plain. CTA to subscribe.",
    },
    {
        "slug": "twistsrevealed",
        "display": "Twists Revealed",
        "handle": "@TwistsRevealed",
        "youtube_channel": "UC_TwistsRevealed",
        "theme": "plot twists, reveals, shocking stories, suspense",
        "voice": "narrative, shock-reveal, suspense-first",
        "title_style": "suspense-first, setup-payoff",
        "caption_style": "quick setup and payoff, suspense-first",
        "hook_style": "shock reveal",
        "visual_style": "narrative stills, tension-building, reveal moment highlighted",
        "emoji_policy": "minimal",
        "primary_category": "Entertainment",
        "keywords": ["plot twist", "reveal", "shocking", "story", "suspense"],
        "posting": {"cadence": "daily", "windows": ["19:00", "21:30"], "timezone": "America/New_York"},
        "kpis": {"target_views_30d": 550000, "target_ctr": 0.065, "target_avg_view_pct": 0.48,
                  "target_subs_per_post": 350, "priority": "watch_time"},
        "thumb_rules": "Setup on left, '?' or shock on right. Tension colors. 2-4 words. "
                       "Never spoil the twist in the thumbnail.",
        "title_rules": "Setup + payoff framing. 'It looked normal... until'. 4-7 words. No spoilers.",
        "caption_rules": "Quick setup, suspense hook, no spoiler. Payoff tease. 3-5 niche hashtags.",
    },
]


def write_brand(b):
    d = BRANDS_DIR / b["slug"]
    d.mkdir(parents=True, exist_ok=True)

    (d / "brand.yaml").write_text(yaml.safe_dump({
        "slug": b["slug"],
        "display_name": b["display"],
        "handle": b["handle"],
        "youtube_channel_id": b["youtube_channel"],
        "master_account": MASTER_EMAIL,
        "theme": b["theme"],
        "voice": b["voice"],
        "visual_style": b["visual_style"],
        "hook_style": b["hook_style"],
        "emoji_policy": b["emoji_policy"],
        "primary_category": b["primary_category"],
        "keywords": b["keywords"],
        "created": "2026-07-15",
        "active": True,
    }, sort_keys=False, allow_unicode=True), encoding="utf-8")

    (d / "sources.yaml").write_text(yaml.safe_dump({
        "long_form_sources": [
            {"type": "youtube_channel", "value": b["handle"],
             "role": "primary", "notes": "Pull next approved long-form upload from this channel."},
        ],
        "ingest": {"strategy": "next_approved", "min_duration_sec": 60, "max_duration_sec": 7200},
        "approval_required": True,
    }, sort_keys=False, allow_unicode=True), encoding="utf-8")

    (d / "style_guide.md").write_text(
        f"# Style Guide — {b['display']}\n\n"
        f"- **Voice:** {b['voice']}\n"
        f"- **Visual style:** {b['visual_style']}\n"
        f"- **Emoji policy:** {b['emoji_policy']}\n"
        f"- **Hook style:** {b['hook_style']}\n"
        f"- **Theme:** {b['theme']}\n\n"
        f"Every clip, title, caption, and thumbnail must read as a {b['display']} asset, "
        f"not a generic MBM clip.\n",
        encoding="utf-8",
    )

    (d / "posting_schedule.yaml").write_text(yaml.safe_dump({
        "cadence": b["posting"]["cadence"],
        "timezone": b["posting"]["timezone"],
        "windows": b["posting"]["windows"],
        "approval_gate": True,
        "brand_aware": True,
    }, sort_keys=False, allow_unicode=True), encoding="utf-8")

    (d / "kpis.yaml").write_text(yaml.safe_dump({
        "target_views_30d": b["kpis"]["target_views_30d"],
        "target_ctr": b["kpis"]["target_ctr"],
        "target_avg_view_pct": b["kpis"]["target_avg_view_pct"],
        "target_subs_per_post": b["kpis"]["target_subs_per_post"],
        "priority_metric": b["kpis"]["priority"],
    }, sort_keys=False, allow_unicode=True), encoding="utf-8")

    (d / "thumbnail_rules.md").write_text(f"# Thumbnail Rules — {b['display']}\n\n{b['thumb_rules']}\n", encoding="utf-8")
    (d / "title_rules.md").write_text(f"# Title Rules — {b['display']}\n\n{b['title_rules']}\n", encoding="utf-8")
    (d / "caption_rules.md").write_text(f"# Caption Rules — {b['display']}\n\n{b['caption_rules']}\n", encoding="utf-8")

    print(f"  wrote {b['slug']}/")


def main():
    BRANDS_DIR.mkdir(parents=True, exist_ok=True)
    for b in BRANDS:
        write_brand(b)
    print(f"Done. {len(BRANDS)} brands under {BRANDS_DIR}")


if __name__ == "__main__":
    main()
