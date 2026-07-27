"""MBM Instagram Intelligence — shared schema and helpers.

Single source of truth for the Reel data model, SQLite databases, content hashing
for incremental sync, and the Markdown renderer that turns a Reel dict into the
document defined by TEMPLATE.md.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# --- Canonical field list (order matters for prompt construction) ---
REEL_FIELDS = [
    "title", "creator", "url", "date_saved", "category", "niche",
    "business_model", "primary_hook", "hook_type", "hook_score", "retention_score",
    "editing_style", "visual_breakdown", "scene_timeline", "caption", "transcript",
    "cta", "psychology_used", "marketing_strategy", "sales_funnel", "monetization_method",
    "offer", "pain_points", "dream_outcome", "audience", "keywords", "hashtags", "music",
    "framework", "how_to_clone", "ai_recreation_prompt", "capcut_prompt", "invideo_prompt",
    "canva_prompt", "midjourney_prompt", "flux_prompt", "chatgpt_prompt", "claude_prompt",
    "gemini_prompt", "thumbnail_prompt", "improvements", "mbm_relevance_score",
    "potential_revenue", "notes",
]

# MBM scoring sub-keys
MBM_SCORE_KEYS = [
    "revenue", "automation", "leadgen", "construction",
    "ai", "twists", "moneybeast",
]

HOOK_TYPES = [
    "Curiosity", "Shock", "Money", "Fear", "Authority", "Story",
    "Problem", "Controversy", "Listicle", "Case Study",
]

PSYCHOLOGY_TRIGGERS = [
    "Scarcity", "Urgency", "Social Proof", "Status", "Greed", "Fear",
    "Novelty", "Authority", "Curiosity Gap", "Identity",
]

BUSINESS_MODELS = [
    "Lead Generation", "Wholesaling", "Land Flipping", "AI Agency", "SaaS",
    "Content Creation", "Affiliate", "SMMA", "Local Services", "Construction",
    "Real Estate", "Investing", "Automation",
]


@dataclass
class Reel:
    reel_id: str
    url: str
    creator: str = ""
    title: str = ""
    date_saved: str = ""
    category: str = ""
    niche: str = ""
    business_model: str = ""
    primary_hook: str = ""
    hook_type: str = ""
    hook_score: int = 0
    retention_score: int = 0
    editing_style: str = ""
    visual_breakdown: str = ""
    scene_timeline: str = ""
    caption: str = ""
    transcript: str = ""
    cta: str = ""
    psychology_used: str = ""
    marketing_strategy: str = ""
    sales_funnel: str = ""
    monetization_method: str = ""
    offer: str = ""
    pain_points: str = ""
    dream_outcome: str = ""
    audience: str = ""
    keywords: str = ""
    hashtags: str = ""
    music: str = ""
    framework: str = ""
    how_to_clone: str = ""
    ai_recreation_prompt: str = ""
    capcut_prompt: str = ""
    invideo_prompt: str = ""
    canva_prompt: str = ""
    midjourney_prompt: str = ""
    flux_prompt: str = ""
    chatgpt_prompt: str = ""
    claude_prompt: str = ""
    gemini_prompt: str = ""
    thumbnail_prompt: str = ""
    improvements: str = ""
    mbm_relevance_score: int = 0
    potential_revenue: str = ""
    notes: str = ""
    mbm_scores: dict = field(default_factory=dict)
    raw: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: _now())

    def to_dict(self) -> dict:
        d = asdict(self)
        return d

    def content_hash(self) -> str:
        """Hash of the volatile parts used for incremental sync."""
        blob = json.dumps(
            {
                "url": self.url,
                "caption": self.caption,
                "transcript": self.transcript,
                "creator": self.creator,
                "hook_score": self.hook_score,
                "mbm_relevance_score": self.mbm_relevance_score,
            },
            sort_keys=True,
        )
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def slugify(text: str, max_len: int = 60) -> str:
    text = (text or "untitled").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:max_len] or "untitled"


def reel_id_from_url(url: str) -> str:
    """Extract a stable id from an Instagram reel URL."""
    m = re.search(r"(?:reel|p)/([A-Za-z0-9_-]+)", url or "")
    if m:
        return m.group(1)
    return hashlib.sha1((url or "").encode()).hexdigest()[:12]


# --- Markdown rendering -------------------------------------------------
_TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "TEMPLATE.md"


def render_markdown(reel: Reel) -> str:
    """Render a Reel to the TEMPLATE.md document format."""
    template = _TEMPLATE_PATH.read_text(encoding="utf-8")
    data = reel.to_dict()
    # Build MBM scoring block values
    scores = reel.mbm_scores or {}
    mapping = {
        "score_revenue": scores.get("revenue", 0),
        "score_automation": scores.get("automation", 0),
        "score_leadgen": scores.get("leadgen", 0),
        "score_construction": scores.get("construction", 0),
        "score_ai": scores.get("ai", 0),
        "score_twists": scores.get("twists", 0),
        "score_moneybeast": scores.get("moneybeast", 0),
    }
    ctx = {**data, **mapping}
    # Replace {{ key }} tokens; missing -> empty
    def _sub(match: re.Match) -> str:
        key = match.group(1).strip()
        val = ctx.get(key, "")
        if isinstance(val, (list, dict)):
            val = json.dumps(val, ensure_ascii=False)
        return str(val)

    out = re.sub(r"\{\{\s*([\w.]+)\s*\}\}", _sub, template)
    return out


def parse_frontmatter(md_text: str) -> tuple[dict, str]:
    """Parse YAML-ish frontmatter (simple key: value) + body."""
    fm: dict[str, Any] = {}
    body = md_text
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", md_text, re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                fm[k.strip()] = v.strip().strip('"')
        body = m.group(2)
    return fm, body


# --- Database setup -----------------------------------------------------
DB_SCHEMA = {
    "knowledge": """
        CREATE TABLE IF NOT EXISTS reels (
            reel_id TEXT PRIMARY KEY,
            url TEXT,
            creator TEXT,
            title TEXT,
            date_saved TEXT,
            category TEXT,
            niche TEXT,
            business_model TEXT,
            hook_type TEXT,
            hook_score INTEGER,
            mbm_relevance_score INTEGER,
            potential_revenue TEXT,
            content_hash TEXT,
            created_at TEXT,
            updated_at TEXT
        );
    """,
    "creators": """
        CREATE TABLE IF NOT EXISTS creators (
            handle TEXT PRIMARY KEY,
            name TEXT,
            post_frequency TEXT,
            top_topics TEXT,
            avg_hook REAL,
            cta_strategy TEXT,
            business_model TEXT,
            audience TEXT,
            offer_ladder TEXT,
            reel_count INTEGER DEFAULT 0,
            updated_at TEXT
        );
    """,
    "hooks": """
        CREATE TABLE IF NOT EXISTS hooks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reel_id TEXT,
            hook_type TEXT,
            hook_text TEXT,
            hook_score INTEGER,
            niche TEXT
        );
    """,
    "offers": """
        CREATE TABLE IF NOT EXISTS offers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reel_id TEXT,
            creator TEXT,
            lead_magnet TEXT,
            tripwire TEXT,
            core_offer TEXT,
            upsell TEXT,
            monetization_method TEXT,
            price_anchoring TEXT
        );
    """,
    "psychology": """
        CREATE TABLE IF NOT EXISTS psychology (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reel_id TEXT,
            trigger TEXT,
            note TEXT
        );
    """,
    "editing": """
        CREATE TABLE IF NOT EXISTS editing (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reel_id TEXT,
            editing_style TEXT,
            cuts_per_minute REAL,
            avg_shot_length REAL,
            subtitle_style TEXT,
            color_palette TEXT,
            hook_timing TEXT,
            cta_timing TEXT
        );
    """,
    "business_models": """
        CREATE TABLE IF NOT EXISTS business_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reel_id TEXT,
            business_model TEXT,
            niche TEXT,
            revenue_potential INTEGER
        );
    """,
}
