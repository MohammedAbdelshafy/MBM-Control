"""Dedupe publish_queue to one canonical package per brand, then regenerate
script-true viral title/caption/hashtags/thumbnail-text via the brand rule files
and the LOCAL Ollama LLM (real inference - not the model_registry fake fallback).

Canonical content mapping (verified from the scripts embedded in the queue):
  dontwatchthis      -> transformed_viral_movie_recap_01.mp4      (dark psych/noir)
  goalmachinez       -> transformed_viral_real_estate_01.mp4      (football free kick)
  cutedosage         -> transformed_viral_make_money_01.mp4       (puppy/kitten cute)
  clippingfactorymbm -> transformed_viral_dark_psychology_01.mp4  (AI voice cold-call)
  twistsrevealed     -> transformed_viral_voice_agency_01.mp4     (murder spying twist)

Output: publish_queue/enhanced/<brand>_viral.json  (single canonical package each).
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SYS_PY = HERE / "mbm_social" / "model_registry.py"

OLLAMA = "http://localhost:11434"
MODEL = "qwen2.5-coder:7b"

CANON = {
    "dontwatchthis": {
        "video": "transformed_viral_movie_recap_01.mp4",
        "script": "Warning! Do not use these five dark psychology techniques unless you want absolute influence. "
                  "Number one: lower your voice to make people lean in. Subscribe if you dare.",
    },
    "goalmachinez": {
        "video": "transformed_viral_real_estate_01.mp4",
        "script": "Unbelievable! Look at this incredible curve on the free kick! Right into the top corner, "
                  "leaving the goalkeeper helpless. Welcome to Goal Machinez!",
    },
    "cutedosage": {
        "video": "transformed_viral_make_money_01.mp4",
        "script": "Get ready for your daily dose of pure happiness! Watch this puppy and kitten share the most "
                  "adorable playtime ever. Subscribe to Cute Dosage!",
    },
    "clippingfactorymbm": {
        "video": "transformed_viral_dark_psychology_01.mp4",
        "script": "Behind the scenes of our 24/7 AI Voice Cold Calling Swarm! Replacing 5 SDRs with automated "
                  "AI agents that call 1,000 leads per minute.",
    },
    "twistsrevealed": {
        "video": "transformed_viral_voice_agency_01.mp4",
        "script": "A bored teenager decides to spy on his neighbor with binoculars. But tonight he witnesses a "
                  "cold-blooded murder. Now the killer turns around and looks directly into his camera.",
    },
}


def ollama(prompt: str, system: str, max_tokens: int = 160, temp: float = 0.4) -> str:
    payload = {
        "model": MODEL,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "options": {"temperature": temp, "num_predict": max_tokens},
    }
    req = urllib.request.Request(
        f"{OLLAMA}/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read()).get("response", "").strip()


def ollama_ok() -> bool:
    try:
        with urllib.request.urlopen(f"{OLLAMA}/api/tags", timeout=4) as r:
            data = json.load(r)
        return MODEL in {m["name"] for m in data.get("models", [])}
    except Exception:
        return False


def read_file(p: Path) -> str:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return ""


def enhance_brand(slug: str, canon: dict) -> dict:
    bdir = HERE / "Brands" / slug
    brand = {}
    for ln in read_file(bdir / "brand.yaml").splitlines():
        if ":" in ln and not ln.strip().startswith("#"):
            k, v = ln.split(":", 1)
            brand[k.strip()] = v.strip()
    title_rules = read_file(bdir / "title_rules.md")
    caption_rules = read_file(bdir / "caption_rules.md")
    thumb_rules = read_file(bdir / "thumbnail_rules.md")
    name = brand.get("display_name", slug)
    handle = brand.get("handle", "")
    keywords = [ln.strip("- \t") for ln in read_file(bdir / "brand.yaml").splitlines() if ln.strip().startswith("-")]
    if not keywords:
        keywords = brand.get("keywords", "").split(",") if isinstance(brand.get("keywords"), str) else []
    script = canon["script"]

    def ask(system: str, prompt: str, tokens: int, temp: float = 0.4) -> str:
        out = ollama(prompt, system, tokens, temp)
        return out.strip().strip('"').strip()

    title = ask(
        f"You are a YouTube Shorts title writer for the channel '{name}'. Rules:\n{title_rules}\n\n"
        "Return ONLY the final title. No quotes, no explanation.",
        f"Clip narration: {script}\n\nWrite the viral title now:",
        60, 0.7,
    )
    caption = ask(
        f"You write YouTube Shorts descriptions for '{name}'. Rules:\n{caption_rules}",
        f"Clip narration: {script}\n\nWrite the 1-2 sentence description (curiosity gap, no spoilers). No hashtags.",
        200,
    )
    tags = ask(
        "Return ONLY a JSON array of 5 YouTube hashtags for a Short. No other text.",
        f"Brand: {name}. Topic: {script[:220]}. Niche words: {', '.join(keywords[:8])}.",
        120,
    )
    try:
        cleaned = tags.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(cleaned) if cleaned.startswith("[") else json.loads("[" + cleaned.split("]")[0].split("[")[-1] + "]")
        tag_list = [str(t).strip() for t in parsed if str(t).strip()]
    except Exception:
        import re as _re
        tag_list = _re.findall(r"#[\w-]+", tags)
    tag_list = [(t if t.startswith("#") else "#" + t) for t in tag_list][:6]

    thumb = ask(
        f"You design YouTube thumbnail overlays for '{name}'. Rules:\n{thumb_rules}\n\n"
        "Return ONLY the overlay text, max 3 words, no quotes.",
        f"Video title: {title}\nScript: {script[:160]}",
        60,
    )

    return {
        "brand": slug,
        "display_name": name,
        "handle": handle,
        "youtube_channel_id": brand.get("youtube_channel_id", f"UC_{slug}"),
        "niche": brand.get("primary_category", ""),
        "video_path": str(HERE / "viral_pool" / canon["video"]),
        "script": script,
        "title": clean_yt(title)[:100],
        "description": clean_yt(caption),
        "hashtags": tag_list,
        "thumbnail_text": clean_yt(thumb),
        "status": "draft",
        "enhanced_by": "virality_enhancer",
        "enhanced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "published_platforms": {"youtube": False, "instagram": False, "tiktok": False},
    }


def clean_yt(s: str) -> str:
    import re
    s = s.replace("\n", " ").strip()
    s = re.sub(r'\s+', ' ', s)
    return s


def extract(t: str) -> str:
    if not t:
        return ""
    import re
    m = re.search(r'([A-Za-z0-9][^"\n]{0,90})', t)
    return (m.group(1) if m else t.split("\n")[0]).strip()


def main():
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not ollama_ok():
        print("OLLAMA MODEL NOT AVAILABLE - aborting (won't fabricate).")
        sys.exit(2)
    out_dir = HERE / "publish_queue"
    out_dir.mkdir(exist_ok=True)
    for slug, canon in CANON.items():
        print(f"\n### {slug}")
        try:
            pkg = enhance_brand(slug, canon)
        except Exception as e:
            print(f"  FAILED: {e}")
            continue
        dest = out_dir / f"enhanced_{slug}_viral.json"
        dest.write_text(json.dumps(pkg, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  -> {dest.name}")
        print(f"     title: {pkg['title']}")
        print(f"     desc:  {pkg['description'][:90]}")
        print(f"     tags:  {' '.join(pkg['hashtags'])}")
        print(f"     thumb: {pkg['thumbnail_text']}")


if __name__ == "__main__":
    main()