"""
content_intelligence -- Generate hook/title/description/caption/hashtags/CTA (Phase 3).

Uses the existing Model Registry (local Ollama-first inference) — never hardcodes
a model name. Historical winning patterns can be passed in via `history` (sourced
from the learning engine) so generations improve over time. When the model is
unavailable the functions degrade to deterministic, clearly-labelled templates
rather than inventing statistics.
"""
from __future__ import annotations

from typing import Any, Optional

from . import model_registry as mr
from . import brand_config as bc


def _load_brand(slug: str) -> dict:
    try:
        return bc.load_brand(slug)
    except Exception:
        return {
            "display_name": slug or "MBM",
            "voice": "concise, high-energy",
            "title_rules": "max 100 chars, curiosity-driven",
            "caption_rules": "1-3 sentences, native tone",
        }


def generate_hook(brand_slug: str, topic: str, transcript_window: str = "",
                  history: Optional[list[str]] = None) -> tuple[str, str]:
    brand = _load_brand(brand_slug)
    hist = ""
    if history:
        hist = "Winning hooks from memory: " + " | ".join(history[:5]) + ". "
    sys = (f"You write scroll-stopping opening hooks for the brand "
           f"'{brand['display_name']}'. Voice: {brand['voice']}.")
    prompt = (f"Topic: {topic}\nContext: {transcript_window[:400]}\n"
              f"{hist}Write ONE hook (max 18 words, no hashtags).")
    try:
        model = mr.resolve("hook_generation")
        out = mr.generate(prompt, task="hook_generation", system=sys, max_tokens=60, temperature=0.8)
        if out:
            return out.strip().split("\n")[0][:200], model
    except Exception:
        pass
    fb = f"You won't believe what happens next in {topic}.".replace("  ", " ")
    return fb, "template-fallback"


def generate_metadata(clip: dict, brand_slug: str, platform: str,
                      topic: str = "", audience: str = "",
                      history: Optional[dict] = None) -> dict:
    """Produce a full metadata bundle for one clip.

    `history` may include {"hooks": [...], "titles": [...], "captions": [...],
    "hashtags": [...]} from the learning memory.
    """
    brand = _load_brand(brand_slug)
    hist = history or {}
    hook, hook_model = generate_hook(brand_slug, topic or clip.get("topic", ""),
                                     clip.get("transcript_window", ""), hist.get("hooks"))
    transcript = clip.get("transcript_window", "")
    title_sys = (f"You write {platform} titles for '{brand['display_name']}'. "
                 f"Rules:\n{brand['title_rules']}\nVoice: {brand['voice']}")
    title_prompt = f"Hook: {hook}\nTranscript: {transcript[:800]}\nReturn ONLY the title, max 100 chars."
    try:
        title_model = mr.resolve("title_generation")
        title = mr.generate(title_prompt, task="title_generation", system=title_sys, max_tokens=80)
        title = (title or "").strip().split("\n")[0][:100] or hook
    except Exception:
        title, title_model = f"{brand['display_name']}: {hook}"[:100], "template-fallback"

    cap_sys = (f"You write {platform} descriptions for '{brand['display_name']}'. "
               f"Rules:\n{brand['caption_rules']}")
    cap_prompt = f"Hook: {hook}\nTranscript: {transcript[:800]}\nWrite 1-3 sentence description, no hashtags."
    try:
        cap_model = mr.resolve("caption_generation")
        caption = mr.generate(cap_prompt, task="caption_generation", system=cap_sys, max_tokens=220)
        caption = (caption or "").strip()
    except Exception:
        caption, cap_model = f"{hook} {topic}".strip(), "template-fallback"

    # hashtags: template + optional learned set
    base_tags = [f"#{brand_slug}", "#shorts", f"#{platform}"]
    learned = [f"#{t}" for t in hist.get("hashtags", [])[:5]]
    hashtags = list(dict.fromkeys(base_tags + learned))[:8]

    cta, cta_model = generate_cta(brand_slug, platform, hist.get("ctas"))
    return {
        "hook": hook,
        "hook_model": hook_model,
        "title": title,
        "title_model": title_model,
        "description": caption,
        "caption_model": cap_model,
        "hashtags": hashtags,
        "cta": cta,
        "cta_model": cta_model,
        "platform": platform,
        "brand": brand_slug,
    }


def generate_cta(brand_slug: str, platform: str,
                 history: Optional[list[str]] = None) -> tuple[str, str]:
    sys = (f"You write call-to-actions for the brand '{brand_slug}' on {platform}. "
           f"Encourage follow/subscribe/comment without being spammy.")
    prompt = "Write ONE short CTA (max 12 words)."
    try:
        model = mr.resolve("cta_generation")
        out = mr.generate(prompt, task="cta_generation", system=sys, max_tokens=40)
        if out:
            return out.strip().split("\n")[0][:120], model
    except Exception:
        pass
    return "Follow for more. Comment what you think.", "template-fallback"
