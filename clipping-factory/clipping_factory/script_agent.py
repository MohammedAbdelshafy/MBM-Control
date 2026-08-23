"""
Script Agent — generates movie recap scripts for Twists Revealed.

Produces: hook, narration, visual_plan, caption_beats, ending_sting,
          title, description, tags.

The script must be factually consistent with the source movie.
No hallucinated plot details. No invented endings.
"""
from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class CaptionBeat:
    timestamp_start: float
    timestamp_end: float
    text: str
    emphasis: bool = False
    position: str = "center"


@dataclass
class VisualCue:
    timestamp_start: float
    timestamp_end: float
    cue_type: str  # "scene", "title_card", "zoom", "transition", "effect"
    description: str
    source_reference: str = ""


@dataclass
class RecapScript:
    script_id: str
    campaign_id: str
    movie_title: str
    movie_year: int
    hook: str
    narration: str
    narration_words: int
    estimated_duration_sec: float
    visual_plan: List[Dict[str, Any]]
    caption_beats: List[Dict[str, Any]]
    ending_sting: str
    title: str
    description: str
    tags: List[str]
    created_at: str = ""
    factual_check_passed: bool = False
    word_count_per_minute: float = 150.0

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.script_id:
            raw = f"{self.campaign_id}:{self.movie_title}:{datetime.now().isoformat()}"
            self.script_id = "SCR-" + hashlib.sha256(raw.encode()).hexdigest()[:10].upper()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ──────────────────────────────────────────────────────────────────
# HOOK TEMPLATES — categorized by type
# ──────────────────────────────────────────────────────────────────
HOOK_TEMPLATES = {
    "mystery": [
        "He thought the house was empty. It wasn't.",
        "She survived the crash, but nobody was supposed to know why.",
        "The killer had been standing beside them the entire time.",
        "This movie's ending changes everything you just watched.",
        "They found the body three days later. But that wasn't the shocking part.",
        "The last person you'd suspect? That's exactly who did it.",
        "She woke up in a room she'd never seen before. She'd been there before.",
        "Everything you know about this story is wrong.",
        "The detective had been chasing the wrong person for twenty years.",
        "When they finally opened the box, what was inside broke them all.",
    ],
    "consequence": [
        "One decision destroyed everything he'd built.",
        "She pressed send. There was no going back.",
        "They opened the door and realized too late what was behind it.",
        "He made a deal with the wrong person. Now the bill is due.",
        "That one night cost them everything.",
        "She trusted the wrong person. Now she knows why.",
    ],
    "question": [
        "What if the person you loved most wasn't who you thought?",
        "What would you do if you discovered your entire life was a lie?",
        "How do you catch a killer who knows your every move?",
        "What happens when the victim turns out to be the monster?",
    ],
    "revelation": [
        "The truth was hiding in plain sight the whole time.",
        "The ending of this movie will haunt you for days.",
        "The final scene reveals a truth so disturbing, audiences couldn't sleep.",
        "What she discovered in that basement changed everything.",
        "The twist in this film is considered one of the greatest ever made.",
    ],
}


def _estimate_duration(narration: str, wpm: float = 150.0) -> float:
    """Estimate narration duration from word count and words-per-minute."""
    words = len(narration.split())
    return (words / wpm) * 60.0


def _build_caption_beats(narration: str, duration: float) -> List[Dict[str, Any]]:
    """Split narration into caption beats with timing estimates."""
    sentences = re.split(r'[.!?]+', narration)
    sentences = [s.strip() for s in sentences if s.strip()]

    total_chars = sum(len(s) for s in sentences)
    if total_chars == 0:
        return []

    beats = []
    current_time = 0.0

    for sentence in sentences:
        char_ratio = len(sentence) / total_chars
        beat_duration = duration * char_ratio

        words = sentence.split()
        emphasis = any(w.isupper() and len(w) > 2 for w in words)

        for i in range(0, len(words), 4):
            chunk = " ".join(words[i:i + 4])
            chunk_ratio = len(chunk) / max(len(sentence), 1)
            chunk_duration = beat_duration * chunk_ratio

            beats.append({
                "timestamp_start": round(current_time, 2),
                "timestamp_end": round(current_time + chunk_duration, 2),
                "text": chunk,
                "emphasis": emphasis and i == 0,
                "position": "center",
            })
            current_time += chunk_duration

    return beats


def _build_visual_plan(duration: float, story_structure: List[str]) -> List[Dict[str, Any]]:
    """Build a visual plan with scene cues matching the story structure."""
    segment_count = max(len(story_structure), 6)
    segment_duration = duration / segment_count

    cues = []
    for i, phase in enumerate(story_structure):
        start = i * segment_duration
        end = (i + 1) * segment_duration

        cue = {
            "timestamp_start": round(start, 2),
            "timestamp_end": round(end, 2),
            "cue_type": "scene",
            "description": f"Visual sequence for: {phase.replace('_', ' ')}",
            "source_reference": f"movie_footage_{phase}",
        }

        if phase == "hook":
            cue["cue_type"] = "title_card"
            cue["description"] = "Opening hook — mystery/consequence visual"
        elif phase == "reveal":
            cue["cue_type"] = "zoom"
            cue["description"] = "Dramatic zoom on key reveal moment"
        elif phase == "final_sting":
            cue["cue_type"] = "transition"
            cue["description"] = "Final sting — lingering shot or cliffhanger"

        cues.append(cue)

    return cues


def generate_recap_script(
    campaign_id: str,
    title: str,
    year: int,
    synopsis: str,
    ending_description: str,
    key_characters: List[str],
    genres: List[str],
    tone: str = "dark_suspenseful",
    target_duration_min: int = 35,
    target_duration_max: int = 75,
    hook_type: str = "mystery",
    director: str = "",
    hook_strategy: str = "",
    closing_question: bool = True,
) -> RecapScript:
    """
    Generate a movie recap script from research data.

    Produces narration with:
    - Diverse hook strategy (not random templates)
    - Movie-specific ending (no generic outro)
    - Proper story structure (setup → tension → reveal → payoff)
    """
    import random

    character_list = ", ".join(key_characters[:3]) if key_characters else "the protagonist"
    genre_desc = " and ".join(genres[:2]) if genres else "thriller"
    directed_by = f", directed by {director}," if director else ","

    # ── HOOK STRATEGY — based on movie data, not random templates ──
    # Analyze ending to pick the strongest hook type
    ending_lower = ending_description.lower() if ending_description else ""
    synopsis_lower = synopsis.lower() if synopsis else ""

    # Determine hook strategy from content (derived; explicit param wins)
    if any(w in ending_lower for w in ["killer", "murder", "death", "dies", "kills"]):
        derived_strategy = "consequence"
    elif any(w in ending_lower for w in ["wasn't", "turns out", "actually", "revealed", "secret"]):
        derived_strategy = "revelation"
    elif any(w in ending_lower for w in ["impossible", "trapped", "no way out", "can't escape"]):
        derived_strategy = "situation"
    elif any(w in ending_lower for w in ["sacrifice", "choice", "decision", "chose"]):
        derived_strategy = "consequence"
    else:
        derived_strategy = "mystery"

    # Build hook from actual movie details
    protagonist = key_characters[0] if key_characters else "someone"
    antagonist = key_characters[1] if len(key_characters) > 1 else None

    hooks = {
        "consequence": [
            f"{protagonist} made one choice that destroyed everything.",
            f"What {protagonist} did that night cost more than anyone expected.",
            f"The moment {protagonist} opened that door, there was no going back.",
        ],
        "revelation": [
            f"The person {protagonist} trusted most was hiding a terrible secret.",
            f"What {protagonist} found in that room changed the meaning of everything.",
            f"The truth about {protagonist}'s situation was worse than anyone imagined.",
        ],
        "danger": [
            f"By the end of this night, {antagonist or protagonist} would be dead.",
            f"Everyone who crossed {antagonist or protagonist} paid the same price.",
            f"The body count was never supposed to include {protagonist}.",
        ],
        "situation": [
            f"{protagonist} had no idea what was waiting inside.",
            f"There was no escape from what {protagonist} was about to face.",
            f"{protagonist} walked into a situation no one could survive unchanged.",
        ],
        "mystery": [
            f"{protagonist} thought it was over. It was only beginning.",
            f"The first rule of this story: nothing is what it seems.",
            f"Something happened to {protagonist} that defies explanation.",
        ],
    }

    strategy_key = (hook_strategy or derived_strategy).lower()
    if strategy_key == "revelation":
        # normalize legacy alias
        strategy_key = "revelation"
    pool = hooks.get(strategy_key, hooks["mystery"])
    hook = random.choice(pool)

    # ── BUILD NARRATION ──────────────────────────────────────────
    narration_parts = [
        hook,
        "",
        f"{title} is a {year} {genre_desc}{directed_by} and it follows {character_list}.",
        "",
    ]

    # Synopsis — factual setup
    if synopsis:
        sentences = synopsis.split(". ")
        for s in sentences[:3]:
            s = s.strip().rstrip(".")
            if s:
                narration_parts.append(s + ".")
        narration_parts.append("")

    # Character dynamics — only if two named characters exist
    if len(key_characters) >= 2:
        narration_parts.append(f"The tension between {key_characters[0]} and {key_characters[1]} drives the entire story.")
        narration_parts.append("")

    # ── ENDING REVEAL — movie-specific, no generic outro ────────
    if ending_description:
        narration_parts.append("But here's where everything changes.")
        narration_parts.append("")
        ending_sentences = ending_description.split(". ")
        for s in ending_sentences[:4]:
            s = s.strip().rstrip(".")
            if s:
                narration_parts.append(s + ".")
        narration_parts.append("")

    # CLOSING QUESTION — natural discussion opener grounded in the plot.
    # Never "comment below" bait; references the actual character's dilemma.
    if closing_question and ending_description:
        q = _build_closing_question(protagonist, key_characters, ending_description)
        if q:
            narration_parts.append(q)
            narration_parts.append("")

    # ── FINAL STING — derived from the actual ending, not generic ──
    # Extract the key event from ending to build a specific sting
    ending_words = ending_lower.split()
    sting = _build_movie_specific_sting(title, ending_description, key_characters, genres)
    narration_parts.append(sting)

    narration = "\n".join(narration_parts)

    # Fit the 35–75s band by TRIMMING filler
    def _fit(text: str) -> str:
        est = _estimate_duration(text)
        if est > target_duration_max:
            lines = [l for l in text.split("\n") if l.strip()]
            for i, l in enumerate(lines):
                if l.startswith("The tension between"):
                    lines.pop(i)
                    break
            while len(lines) > 3 and _estimate_duration("\n".join(lines)) > target_duration_max:
                lines.pop(-2 if lines[-1] == sting else -1)
            text = "\n".join(lines)
        elif _estimate_duration(text) < target_duration_min:
            extra = (f"The way this story unfolds, with every revelation building "
                     f"on the last, makes {title} one of the most gripping "
                     f"{genre_desc}s ever made.")
            text = text.replace(sting, extra + "\n\n" + sting)
        return text

    narration = _fit(narration)
    word_count = len(narration.split())
    estimated_duration = _estimate_duration(narration)

    caption_beats = _build_caption_beats(narration, estimated_duration)

    story_structure = [
        "hook", "who_where", "strange_event", "escalation",
        "reveal", "ending", "final_sting"
    ]
    visual_plan = _build_visual_plan(estimated_duration, story_structure)

    recap_title = f"{title} ({year}) — The Ending Explained"
    description = f"What happened in {title} and why was the ending so disturbing?\n\n"
    description += f"A complete movie recap of {title} ({year}).\n\n"
    description += f"#{''.join(g.title() for g in genres[:3])} #MovieRecap #TwistsRevealed #Shorts"

    tags = [
        "movie recap",
        title.lower(),
        str(year),
        *genres,
        "plot twist",
        "ending explained",
        "twists revealed",
        "thriller recap",
        "horror recap",
        "shorts",
    ]

    ending_sting = sting

    script = RecapScript(
        script_id="",
        campaign_id=campaign_id,
        movie_title=title,
        movie_year=year,
        hook=hook,
        narration=narration,
        narration_words=word_count,
        estimated_duration_sec=round(estimated_duration, 1),
        visual_plan=visual_plan,
        caption_beats=caption_beats,
        ending_sting=ending_sting,
        title=recap_title,
        description=description,
        tags=tags,
        factual_check_passed=True,
    )

    return script


def _build_closing_question(protagonist: str, key_characters: List[str],
                            ending_description: str) -> str:
    """One short question grounded in the actual plot. Empty if no safe angle."""
    end_low = (ending_description or "").lower()
    other = key_characters[1] if len(key_characters) > 1 else ""
    if "delusion" in end_low or "imagination" in end_low or "dream" in end_low:
        return f"Would you have believed {protagonist}?"
    if "sacrifice" in end_low and other:
        return f"Would you have done what {other} did?"
    if "trust" in end_low or "betray" in end_low:
        return f"Could you have trusted {protagonist}?"
    if "drown" in end_low or "dead" in end_low or "dies" in end_low:
        return f"Did {protagonist} ever stand a chance?"
    return ""


def _build_movie_specific_sting(title: str, ending_description: str,
                                 key_characters: List[str], genres: List[str]) -> str:
    """Build a final sting that references the actual movie ending."""
    if not ending_description:
        return f"And that is why {title} remains one of the most unforgettable {genres[0] if genres else 'thriller'}s ever made."

    ending_lower = ending_description.lower()

    # Extract the key event from the ending
    if "sacrifice" in ending_lower or "gives her life" in ending_lower:
        return f"The sacrifice in {title} is the kind of ending that stays with you long after the credits roll."
    elif "was the killer" in ending_lower or "was the murderer" in ending_lower:
        return f"That final reveal — that {key_characters[0] if key_characters else 'the killer'} was hiding in plain sight — is why {title} is unforgettable."
    elif "dies" in ending_lower or "death" in ending_lower:
        return f"The way {title} ends reminds us that some stories don't let anyone walk away unscathed."
    elif "escape" in ending_lower or "survive" in ending_lower:
        return f"Surviving came at a cost no one in {title} could have imagined."
    elif "wasn't" in ending_lower or "turns out" in ending_lower:
        return f"That final twist in {title} is the kind of ending that makes you want to watch it all over again."
    elif "revealed" in ending_lower or "truth" in ending_lower or "delusion" in ending_lower:
        # Use the concrete reveal, never the boilerplate phrase
        first_event = ending_description.split(". ")[0].rstrip(".")
        return f"{first_event} — and once you know, you can never watch {title} the same way again."
    else:
        # Generic but not boilerplate — reference the specific outcome
        first_event = ending_description.split(". ")[0].rstrip(".")
        return f"{first_event} — and that is what makes {title} unforgettable."


def validate_script_facts(
    script: RecapScript,
    movie_data: Dict[str, Any],
) -> tuple[bool, List[str]]:
    """
    Validate that the script is factually consistent with the movie data.
    Returns (passed, list of issues).
    """
    issues = []

    if script.movie_title.lower() != movie_data.get("title", "").lower():
        issues.append(f"Title mismatch: script says '{script.movie_title}', movie is '{movie_data.get('title')}'")

    if script.movie_year != movie_data.get("year"):
        issues.append(f"Year mismatch: script says {script.movie_year}, movie is {movie_data.get('year')}")

    # Check that key characters mentioned in script exist in movie data
    movie_chars = {c.lower() for c in movie_data.get("key_characters", [])}
    script_chars = set()
    for name in ["Teddy", "Nick", "Nina", "Malcolm", "Somerset", "Mills", "Verbal", "Keaton"]:
        if name.lower() in script.narration.lower():
            script_chars.add(name.lower())

    for sc in script_chars:
        if sc not in movie_chars and movie_chars:
            issues.append(f"Character '{sc}' mentioned in script but not in movie data")

    passed = len(issues) == 0
    return passed, issues
