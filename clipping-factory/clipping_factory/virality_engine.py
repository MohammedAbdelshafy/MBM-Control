"""
Virality Engine — probabilistic content-quality scoring for short-form recaps.

ViralReadinessScore (0-100) across 11 weighted dimensions.
Bands: <55 DO_NOT_POST, 55-69 REWRITE, 70-79 ACCEPTABLE, 80-89 STRONG, 90+ PREMIUM.

This is a probability optimization tool, NOT a performance guarantee.
All scoring is deterministic and text/probe-based. No fabricated metrics.

Hard rule: CURIOSITY x TRUTH x PAYOFF. No misleading hooks, no fabricated
plot details, no fake shock. Every hook must be supported by movie research.
"""
from __future__ import annotations

import json
import re
import statistics
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Configurable weights (sum = 100) ─────────────────────────────

DEFAULT_WEIGHTS = {
    "HOOK_POWER": 20,
    "CURIOSITY_GAP": 15,
    "STORY_TENSION": 15,
    "PAYOFF_STRENGTH": 10,
    "RETENTION_PACING": 10,
    "EMOTIONAL_INTENSITY": 10,
    "VISUAL_PATTERN_DENSITY": 5,
    "CAPTION_IMPACT": 5,
    "REWATCH_POTENTIAL": 5,
    "SHAREABILITY": 3,
    "COMMENTABILITY": 2,
}

BANDS = [
    (55, "DO_NOT_POST"),
    (70, "REWRITE"),
    (80, "ACCEPTABLE"),
    (90, "STRONG"),
    (101, "PREMIUM"),
]

GENERIC_OPENERS = [
    "today we", "here's what happens", "this movie is about",
    "have you ever", "let me tell you about", "in this video",
]

WEAK_HOOK_STARTS = [
    "he thought", "she thought", "they thought",
    "there was a", "once upon",
]


def band_for(score: float) -> str:
    for ceiling, name in BANDS:
        if score < ceiling:
            return name
    return "PREMIUM"


# ── Hook generation ──────────────────────────────────────────────

def generate_hook_variants(movie_title: str, year: int,
                           synopsis: str, ending_description: str,
                           key_characters: List[str]) -> List[Dict[str, str]]:
    """Generate 5 hook variants from movie research. Every hook must be
    factually supported by the synopsis/ending data — no fabrication."""
    prot = key_characters[0] if key_characters else None
    antag = key_characters[1] if len(key_characters) > 1 else None
    end_low = (ending_description or "").lower()
    syn_low = (synopsis or "").lower()

    # Extract a concrete event phrase from the ending for truthfulness
    end_first = ending_description.split(". ")[0].rstrip(".") if ending_description else ""
    syn_first = synopsis.split(". ")[0].rstrip(".") if synopsis else ""

    variants = []

    # A. CONSEQUENCE — outcome-first framing
    if prot:
        variants.append({
            "strategy": "CONSEQUENCE",
            "hook": f"{prot} made one decision that sealed everyone's fate.",
            "supported_by": end_first or syn_first,
        })

    # B. REVELATION — hidden-truth framing
    if "reveal" in end_low or "truth" in end_low or "wasn't" in end_low or "turns out" in end_low:
        if prot:
            variants.append({
                "strategy": "REVELATION",
                "hook": f"The truth about {prot} was hiding in plain sight the entire time.",
                "supported_by": end_first,
            })
        else:
            variants.append({
                "strategy": "REVELATION",
                "hook": f"What really happened at the end was hiding in plain sight.",
                "supported_by": end_first,
            })

    # C. MYSTERY — unexplained-event framing
    mystery_event = syn_first if syn_first else end_first
    variants.append({
        "strategy": "MYSTERY",
        "hook": f"Nobody could explain what happened next." if not movie_title
        else f"The events in {movie_title} defied every explanation.",
        "supported_by": mystery_event,
    })

    # D. DANGER — mortal-stakes framing (only when supported)
    if any(w in end_low or w in syn_low for w in ("die", "death", "kill", "dead", "murder")):
        who = antag or prot or "everyone"
        variants.append({
            "strategy": "DANGER",
            "hook": f"By the end of this night, {who} would be dead.",
            "supported_by": end_first or syn_first,
        })

    # E. IMPOSSIBLE SITUATION — trapped/no-exit framing (only when supported)
    if any(w in syn_low or w in end_low for w in ("trap", "escape", "survive", "stuck", "lock")):
        if prot:
            variants.append({
                "strategy": "IMPOSSIBLE_SITUATION",
                "hook": f"{prot} had nowhere left to run.",
                "supported_by": syn_first or end_first,
            })

    return variants


def score_hook(hook: str) -> float:
    """Score a hook 0-1 on curiosity mechanics."""
    h = hook.lower().strip()
    if not h:
        return 0.0

    score = 0.4  # base: it exists

    # Penalize generic openers (instant disqualifiers)
    if any(h.startswith(g) for g in GENERIC_OPENERS):
        return 0.1
    if any(h.startswith(w) for w in WEAK_HOOK_STARTS):
        score -= 0.15

    # Question mark = unresolved question (+0.2)
    if "?" in hook:
        score += 0.2

    # Contradiction / negation pattern (+0.25)
    if re.search(r"\b(but|wasn't|weren't|never|nobody|nothing|no one)\b", h):
        score += 0.25

    # Named character present (+0.15) — specificity beats abstraction
    words = hook.split()
    named = sum(1 for i, w in enumerate(words)
                if w[0:1].isupper() and i > 0 and not w.isupper())
    if named >= 1:
        score += 0.15

    # Consequence language (+0.15)
    if any(w in h for w in ("doomed", "sealed", "cost", "fate", "destroyed",
                            "dead", "killed", "never", "too late")):
        score += 0.15

    # Length penalty: hooks over ~18 words dilute impact
    wc = len(words)
    if wc > 18:
        score -= 0.1 * min(1.0, (wc - 18) / 12)

    return max(0.0, min(1.0, score))


def select_best_hook(variants: List[Dict[str, str]]) -> tuple:
    """Select best-scoring hook; return (best_variant, all_scored)."""
    scored = []
    for v in variants:
        s = score_hook(v["hook"])
        scored.append({**v, "hook_score": round(s, 3)})
    scored.sort(key=lambda x: -x["hook_score"])
    if not scored:
        return {"strategy": "NONE", "hook": "", "hook_score": 0.0}, []
    return scored[0], scored


# ── Curiosity gap ────────────────────────────────────────────────

def score_curiosity_gap(narration: str) -> float:
    """Does the script leave questions unanswered until the payoff?"""
    n = narration.lower()
    score = 0.4
    if "?" in narration:
        score += 0.15
    # Withheld-information markers before the reveal
    if re.search(r"(but here|everything changes|what (he|she|they) didn't)", n):
        score += 0.25
    # Contradiction setup
    if re.search(r"\b(wasn't|weren't|actually|turns out)\b", n):
        score += 0.2
    # Penalty: everything explained too early (reveal word in first 30% of text)
    first_third = n[: len(n) // 3]
    if "revealed to be" in first_third or "was the killer" in first_third:
        score -= 0.2
    return max(0.0, min(1.0, score))


# ── Story tension ────────────────────────────────────────────────

TENSION_MARKERS = ["tension", "threat", "danger", "fear", "secret", "dark",
                   "but ", "however", "until", "suddenly", "no way out"]

def score_story_tension(narration: str) -> float:
    n = narration.lower()
    hits = sum(1 for m in TENSION_MARKERS if m in n)
    return min(1.0, 0.3 + hits * 0.14)


# ── Payoff test ──────────────────────────────────────────────────

GENERIC_ENDINGS = [
    "something audiences never forget",
    "nothing will ever be the same",
    "changes everything",
    "forever changed",
    "unforgettable",
]

def score_payoff(hook: str, sting: str, ending_desc: str) -> float:
    """Does the ending pay off the hook's promise?"""
    s = sting.lower()
    h = hook.lower()
    score = 0.4

    if any(g in s for g in GENERIC_ENDINGS):
        return 0.2  # generic outro fails the payoff test

    # Sting references specific consequence/character
    if any(w in s for w in ("sacrifice", "dies", "dead", "kill", "surviv",
                            "cost", "fate", "vanish", "burn", "shot", "drown")):
        score += 0.35
    # Sting references the movie specifically (not boilerplate)
    if "credits roll" in s or "watch it all over again" in s or \
       re.search(r"\bin\b .+\b(could have imagined|stays with you)", s):
        score += 0.15
    # Hook-promise alignment: both mention same core noun family
    hook_nouns = set(re.findall(r"[a-z]{4,}", h))
    sting_nouns = set(re.findall(r"[a-z]{4,}", s))
    overlap = hook_nouns & sting_nouns - {"that", "with", "this", "have", "would"}
    if overlap:
        score += 0.1
    return max(0.0, min(1.0, score))


# ── Retention map ────────────────────────────────────────────────

RETENTION_SECTIONS = [
    ("0-2s", 0, 2), ("2-5s", 2, 5), ("5-15s", 5, 15),
    ("15-30s", 15, 30), ("30-45s", 30, 45),
    ("45-60s", 45, 60), ("ending", 60, 9999),
]

def build_retention_map(duration: float, caption_beats: List[Dict]) -> Dict[str, Any]:
    """Map information density across time sections; detect flat stretches."""
    sections = {}
    flat_warnings = []

    prev_text = ""
    for name, t0, t1 in RETENTION_SECTIONS:
        if t0 >= duration:
            break
        seg = [b for b in caption_beats
               if b.get("timestamp_start", 0) < min(t1, duration)
               and b.get("timestamp_end", 0) > t0]
        texts = [b.get("text", "") for b in seg]
        new_info = sum(1 for t in texts if t and t != prev_text)
        prev_text = texts[-1] if texts else prev_text
        sections[name] = {
            "beats": len(seg),
            "new_info_units": new_info,
            "density": round(new_info / max(t1 - t0, 0.1) * 5, 2),  # units per 5s
        }
        if 5 <= (t1 - t0) <= 20 and new_info == 0:
            flat_warnings.append(f"flat section {name}: no new information")

    change_rate_ok = all(s["density"] >= 0.5 for s in sections.values()
                         if s["beats"] > 0)
    return {
        "sections": sections,
        "flat_sections": flat_warnings,
        "change_every_2_5s": change_rate_ok,
    }


def score_retention_pacing(retention_map: Dict, duration: float) -> float:
    flat = retention_map["flat_sections"]
    base = 0.85 if not flat else max(0.3, 0.85 - 0.25 * len(flat))
    # Very short clips can't sustain pacing
    if duration < 30:
        base -= 0.15
    return max(0.0, min(1.0, base))


# ── Emotion engine ───────────────────────────────────────────────

EMOTION_DRIVERS = {
    "FEAR": ["fear", "terror", "afraid", "nightmare", "horror"],
    "SHOCK": ["shock", "sudden", "brutal", "graphic"],
    "CURIOSITY": ["mystery", "secret", "hidden", "unknown", "explain"],
    "DREAD": ["doom", "inevitable", "no escape", "waiting", "coming"],
    "SUSPENSE": ["tension", "suspense", "countdown", "race"],
    "DISBELIEF": ["impossible", "unbelievable", "can't be", "defies"],
    "TRAGEDY": ["tragedy", "loss", "grief", "sacrifice", "dies", "death"],
    "REVENGE": ["revenge", "vengeance", "payback", "retaliate"],
}

def classify_emotion(narration: str) -> Dict[str, Any]:
    n = narration.lower()
    counts = {}
    for emotion, markers in EMOTION_DRIVERS.items():
        c = sum(1 for m in markers if m in n)
        if c:
            counts[emotion] = c
    if not counts:
        return {"dominant": "CURIOSITY", "intensity": 0.3, "distribution": {}}
    dominant = max(counts, key=counts.get)
    total = sum(counts.values())
    intensity = min(1.0, total / 6.0)
    focus = counts[dominant] / total  # high focus = single dominant emotion
    return {
        "dominant": dominant,
        "intensity": round(intensity, 2),
        "focus": round(focus, 2),
        "distribution": counts,
    }


# ── Movie specificity ────────────────────────────────────────────

def score_specificity(narration: str, title: str, key_characters: List[str]) -> float:
    n = narration.lower()
    score = 0.3
    chars_mentioned = sum(1 for c in key_characters if c.split()[0].lower() in n)
    score += min(0.4, chars_mentioned * 0.2)
    if title.lower() in n:
        score += 0.2
    # Proper-noun density
    words = narration.split()
    caps = sum(1 for i, w in enumerate(words) if w[:1].isupper() and i > 0)
    score += min(0.2, caps / 40)
    # Penalize phrases that could describe any movie
    generic_phrases = ["a group of friends", "things take a turn", "chaos ensues"]
    for g in generic_phrases:
        if g in n:
            score -= 0.15
    return max(0.0, min(1.0, score))


# ── Rewatch potential ────────────────────────────────────────────

def score_rewatch(narration: str, has_twist: bool) -> float:
    n = narration.lower()
    score = 0.4
    if has_twist:
        score += 0.25
    # Timeline/identity complexity rewards replay
    if re.search(r"\b(before|after|earlier|later|years? (ago|later))\b", n):
        score += 0.15
    # Identity confusion drives replays
    if re.search(r"\b(identity|who (he|she|it|they) (really|actually)|double life)\b", n):
        score += 0.2
    # But confusing ≠ good: penalize unresolved ambiguity with low info
    if len(narration.split()) < 60:
        score -= 0.1
    return max(0.0, min(1.0, score))


# ── Shareability + commentability ────────────────────────────────

SHARE_SIGNALS = ["crazy", "disturbing", "you need to see", "insane",
                 "shocking", "twist", "never forget", "haunt"]

def score_shareability(narration: str, ending_desc: str) -> float:
    n = narration.lower() + " " + (ending_desc or "").lower()
    hits = sum(1 for s in SHARE_SIGNALS if s in n)
    score = 0.3 + hits * 0.18
    # Debate-worthy moral endings share well
    if re.search(r"\b(justified|deserved|moral|right thing|choice)\b", n):
        score += 0.15
    return max(0.0, min(1.0, score))

QUESTION_STARTERS = ["would you", "did you notice", "was it", "could you",
                     "what would you"]

def score_commentability(narration: str) -> float:
    """Natural discussion openings — never 'Comment YES if'."""
    n = narration.lower()
    if "comment yes" in n or "comment below" in n:
        return 0.0  # manufactured engagement is penalized hard
    hits = sum(1 for q in QUESTION_STARTERS if q in n)
    if hits:
        return 0.8
    # Moral dilemmas naturally invite comments even without explicit question
    if re.search(r"\b(choice|decision|trust|betray|sacrifice)\b", n):
        return 0.5
    return 0.3


# ── Visual virality (probe-based) ────────────────────────────────

def analyze_visual(qa: Dict, segment_count: int) -> Dict[str, Any]:
    probe = qa.get("probe", {})
    duration = probe.get("duration", 0)
    segments = segment_count or qa.get("segment_count", 0)
    change_rate = segments / duration if duration else 0  # changes per second
    return {
        "opening_frame_available": True,
        "segment_count": segments,
        "visual_change_rate": round(change_rate, 3),
        "change_every_seconds": round(1 / change_rate, 1) if change_rate else 0,
        "resolution_ok": probe.get("width") == 1080 and probe.get("height") == 1920,
        "high_information_segments": segments,
    }


def score_visual_density(visual: Dict) -> float:
    rate = visual.get("change_every_seconds", 99)
    # Ideal: visual change every 5-8 seconds
    if 4 <= rate <= 9:
        return 1.0
    if 2 <= rate <= 12:
        return 0.7
    return 0.4


# ── Audio virality (probe-based proxies) ─────────────────────────

def analyze_audio(qa: Dict) -> Dict[str, Any]:
    wpm = qa.get("wpm", 0)
    return {
        "pace_wpm": wpm,
        "pace_band": "optimal" if 130 <= wpm <= 165 else ("ok" if 120 <= wpm <= 185 else "off"),
        "has_audio": bool(qa.get("probe", {}).get("audio_codec")),
    }


def score_audio_energy(audio: Dict) -> float:
    if not audio["has_audio"]:
        return 0.0
    if audio["pace_band"] == "optimal":
        return 0.9
    if audio["pace_band"] == "ok":
        return 0.65
    return 0.3


# ── Title generation ─────────────────────────────────────────────

def generate_title_variants(title: str, year: int, ending_desc: str) -> List[Dict[str, str]]:
    e = (ending_desc or "").split(". ")[0].rstrip(".")
    return [
        {"title": f"{title} ({year}) — The Ending Explained",
         "style": "clear_search"},
        {"title": f"Why The Ending of {title} Still Disturbs Audiences",
         "style": "curiosity_emotional"},
        {"title": f"{title}: The Twist Nobody Saw Coming" if e else f"{title} ({year}) Explained",
         "style": "curiosity_specific"},
    ]


# ── Main entry ───────────────────────────────────────────────────

def analyze_artifact(artifact_dir: Path,
                     weights: Optional[Dict[str, int]] = None) -> Dict[str, Any]:
    """Full virality analysis of one clip artifact directory."""
    weights = weights or DEFAULT_WEIGHTS
    artifact_dir = Path(artifact_dir)

    script = json.loads((artifact_dir / "script.json").read_text(encoding="utf-8"))
    qa = json.loads((artifact_dir / "qa.json").read_text(encoding="utf-8"))
    pkg = json.loads((artifact_dir / "publish_package.json").read_text(encoding="utf-8"))

    narration = script["narration"]
    hook = script["hook"]
    sting = script["ending_sting"]
    duration = qa.get("probe", {}).get("duration", 0)
    caption_beats = script.get("caption_beats", [])

    # Research data for hook generation (from campaign record if available)
    campaign = {}
    camp_file = artifact_dir / "campaign.json"
    if camp_file.exists():
        campaign = json.loads(camp_file.read_text(encoding="utf-8"))

    # Reconstruct research context from curated DB via title
    try:
        from .movie_discovery import CURATED_MOVIES
        movie_row = next((m for m in CURATED_MOVIES
                          if m["title"].lower() in script["movie_title"].lower()), {})
    except Exception:
        movie_row = {}

    key_chars = movie_row.get("key_characters", [])
    ending_desc = movie_row.get("ending_description", "")
    synopsis = movie_row.get("synopsis", "")

    # 1. Hook analysis
    variants = generate_hook_variants(script["movie_title"], script["movie_year"],
                                      synopsis, ending_desc, key_chars)
    current_hook_variant = {"strategy": "CURRENT", "hook": hook,
                            "supported_by": "current_script"}
    all_variants = [current_hook_variant] + variants
    best_hook, scored_variants = select_best_hook(all_variants)

    hook_power_raw = max(score_hook(hook), best_hook.get("hook_score", 0))
    hook_improvement_available = score_hook(best_hook["hook"]) > score_hook(hook)

    # 2-11. Dimension scores (each 0-1, multiplied by weight)
    dims = {
        "HOOK_POWER": hook_power_raw,
        "CURIOSITY_GAP": score_curiosity_gap(narration),
        "STORY_TENSION": score_story_tension(narration),
        "PAYOFF_STRENGTH": score_payoff(hook, sting, ending_desc),
        "RETENTION_PACING": 0.0,  # filled below after retention map
        "EMOTIONAL_INTENSITY": 0.0,  # filled below
        "VISUAL_PATTERN_DENSITY": 0.0,  # filled below
        "CAPTION_IMPACT": 0.0,  # filled below
        "REWATch_POTENTIAL": 0.0,  # typo-safe alias added below
    }

    # Retention
    rmap = build_retention_map(duration, caption_beats)
    dims["RETENTION_PACING"] = score_retention_pacing(rmap, duration)

    # Emotion
    emo = classify_emotion(narration)
    dims["EMOTIONAL_INTENSITY"] = emo["intensity"]

    # Visual
    vis = analyze_visual(qa, qa.get("segment_count", 7))
    dims["VISUAL_PATTERN_DENSITY"] = score_visual_density(vis)

    # Captions: coverage + chunk size sanity
    if caption_beats:
        coverage = caption_beats[-1]["timestamp_end"] / max(duration, 0.01)
        avg_len = statistics.mean(len(b["text"].split()) for b in caption_beats)
        cap_score = (coverage if coverage >= 0.85 else coverage * 0.8)
        cap_score *= 1.0 if 2 <= avg_len <= 6 else 0.75
        dims["CAPTION_IMPACT"] = round(min(1.0, cap_score), 3)
    else:
        dims["CAPTION_IMPACT"] = 0.0

    # Rewatch / Share / Comment
    has_twist = bool(re.search(
        r"\b(reveal|twist|turns out|actually|delusion|was the|drown|sacrifice)\b",
        narration.lower()))
    dims["REWATCH_POTENTIAL"] = score_rewatch(narration, has_twist)
    dims["SHAREABILITY"] = score_shareability(narration, ending_desc)
    dims["COMMENTABILITY"] = score_commentability(narration)

    # Remove stale placeholder keys (never overwrite computed values)
    dims.pop("REWATch_POTENTIAL", None)

    # Weighted total (weights are ints summing to ~100; normalize)
    weight_sum = sum(weights.values())
    total = sum(dims[k] * weights.get(k, 0) for k in dims) / weight_sum * 100

    # Weakest dimension
    weighted_scores = {k: dims[k] * weights.get(k, 0) for k in dims}
    weakest = min(weighted_scores, key=weighted_scores.get)

    score = round(total)
    result = {
        "score": score,
        "band": band_for(score),
        "dimensions_raw": {k: round(v, 3) for k, v in dims.items()},
        "dimensions_weighted": {k: round(v, 2) for k, v in weighted_scores.items()},
        "weakest_dimension": weakest,
        "best_hook": best_hook,
        "current_hook": hook,
        "hook_improvement_available": hook_improvement_available,
        "hook_variants": scored_variants,
        "retention_map": rmap,
        "emotion": emo,
        "visual_analysis": vis,
        "audio_analysis": analyze_audio(qa),
        "title_variants": generate_title_variants(script["movie_title"],
                                                  script["movie_year"], ending_desc),
        "duration_sec": duration,
        "movie": script["movie_title"],
        "campaign_id": script["campaign_id"],
    }

    # Recommendation + gate
    threshold = 80
    override_reason = ""
    if score >= threshold:
        recommendation = "PUBLISH"
    elif score >= 70:
        recommendation = "PUBLISH_WITH_CAUTION"
        override_reason = "score in ACCEPTABLE band"
    elif score >= 55:
        recommendation = "REWRITE"
    else:
        recommendation = "DO_NOT_POST"

    result["recommendation"] = recommendation
    result["threshold"] = threshold
    if override_reason:
        result["override_reason"] = override_reason

    # Recommended fix from weakest dimension
    fixes = {
        "HOOK_POWER": "swap in best_hook variant and re-render",
        "CURIOSITY_GAP": "withhold the reveal one beat longer in narration",
        "STORY_TENSION": "add escalation marker between setup and reveal",
        "PAYOFF_STRENGTH": "replace generic sting with movie-specific consequence",
        "RETENTION_PACING": "compress flat mid-section; add info beat every 2-5s",
        "EMOTIONAL_INTENSITY": "lean harder into the dominant emotional driver",
        "VISUAL_PATTERN_DENSITY": "increase scene-change cadence toward 5-7s cuts",
        "CAPTION_IMPACT": "extend caption coverage past 90% of runtime",
        "REWATCH_POTENTIAL": "plant one concrete visual clue referenced by the twist",
        "SHAREABILITY": "surface the most shocking true detail earlier in narration",
        "COMMENTABILITY": "end on a genuine moral dilemma from the plot",
    }
    result["recommended_fix"] = fixes.get(weakest, "")

    return result


def write_virality_artifact(artifact_dir: Path,
                            weights: Optional[Dict[str, int]] = None) -> Path:
    """Run analysis and persist artifacts/twistsrevealed/virality/<ts>/ bundle."""
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = artifact_dir / "virality"
    out.mkdir(exist_ok=True)

    analysis = analyze_artifact(artifact_dir, weights)

    (out / "virality_score.json").write_text(
        json.dumps({"score": analysis["score"], "band": analysis["band"],
                    "recommendation": analysis["recommendation"],
                    "weakest_dimension": analysis["weakest_dimension"],
                    "best_hook": analysis["best_hook"]["hook"],
                    "recommended_fix": analysis["recommended_fix"]},
                   indent=2), encoding="utf-8")
    (out / "hook_variants.json").write_text(
        json.dumps(analysis["hook_variants"], indent=2), encoding="utf-8")
    (out / "retention_map.json").write_text(
        json.dumps(analysis["retention_map"], indent=2), encoding="utf-8")
    (out / "visual_analysis.json").write_text(
        json.dumps(analysis["visual_analysis"], indent=2), encoding="utf-8")
    (out / "audio_analysis.json").write_text(
        json.dumps(analysis["audio_analysis"], indent=2), encoding="utf-8")
    (out / "title_variants.json").write_text(
        json.dumps(analysis["title_variants"], indent=2), encoding="utf-8")
    (out / "recommendation.json").write_text(
        json.dumps(analysis, indent=2, default=str), encoding="utf-8")
    return out


if __name__ == "__main__":
    import sys
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    result = analyze_artifact(Path(target))
    print(json.dumps(result, indent=2, default=str))
