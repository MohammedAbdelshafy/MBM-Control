"""
Beat-Aligned Visual Engine — maps narration beats to REAL source-film shots.

Replaces uniform time-splits with narration-aligned visual selection:
  - Scene-cut detection finds the film's ACTUAL shot boundaries (ffmpeg).
  - Narration sentences become visual beats grouped at sentence boundaries.
  - Each beat carries phase (HOOK/SETUP/ESCALATION/REVEAL/ENDING/PAYOFF),
    intensity (LOW..PEAK/PAYOFF), and a purpose label.
  - Source windows are selected by phase-position prior + shot-duration fit,
    so visual intensity rises with narrative tension (escalation invariant).

Honest limitation: selection uses positional priors + real cut structure +
shot-duration matching. It does NOT perform content recognition (cannot
verify "this frame shows Ellen"). Purpose labels describe intent, not
verified frame content.

Fallback: if cuts can't be detected, callers fall back to uniform splits.
"""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

# ── Data structures ──────────────────────────────────────────────

@dataclass
class VisualBeat:
    start: float            # output timeline start (sec)
    end: float              # output timeline end (sec)
    narration: str          # the sentence(s) covered
    phase: str              # HOOK/SETUP/ESCALATION/REVEAL/ENDING/PAYOFF
    intensity: str          # LOW/MEDIUM/HIGH/PEAK/PAYOFF
    purpose: str            # explicit visual intent
    transition: str         # cut style into this beat
    source_shots: List[Dict[str, float]]  # [{start,end}] in SOURCE film

    @property
    def duration(self) -> float:
        return self.end - self.start


PHASE_PRIORS = {
    # phase -> (region_start_frac, region_end_frac) of source runtime
    "HOOK":       (0.12, 0.38),
    "SETUP":      (0.06, 0.32),
    "ESCALATION": (0.28, 0.62),
    "REVEAL":     (0.58, 0.86),
    "ENDING":     (0.72, 0.94),
    "PAYOFF":     (0.84, 0.98),
}

INTENSITY_TARGET_SHOT = {
    # intensity -> preferred single-shot length (sec)
    "LOW": 5.0, "MEDIUM": 4.0, "HIGH": 3.0, "PEAK": 2.2, "PAYOFF": 3.5,
}

PHASE_OF_STRUCTURE = [
    # ordered rules: (regex on sentence, phase)
    (r"(would you have|did .* ever stand)", "PAYOFF"),
    (r"(audiences never forget|stays with you|watch it all over again|unforgettable|never watch .+ the same)", "PAYOFF"),
    (r"(but here's where everything changes)", "REVEAL"),
    (r"(revealed|delusion|sacrifice|vanish|truth about|turns out|actually)", "REVEAL"),
    (r"(tension between|drives the entire story)", "ESCALATION"),
]

SETUP_MARKERS = (r"(is a \d{4}|directed by|follows|arrives|travels|begins)", )


def classify_sentence(sentence: str, idx: int, total: int,
                      first_body_idx: int, seen_reveal: bool = False) -> tuple:
    """Return (phase, intensity) for one narration sentence."""
    s = sentence.lower()
    if idx == 0:
        return "HOOK", "HIGH"
    for pat, phase in PHASE_OF_STRUCTURE:
        if re.search(pat, s):
            intens = {"PAYOFF": "PAYOFF", "REVEAL": "PEAK", "ESCALATION": "MEDIUM"}[phase]
            return phase, intens
    # post-reveal descent: consequence settling before the payoff question
    if seen_reveal:
        return "ENDING", "MEDIUM"
    if re.search(SETUP_MARKERS[0], s):
        return "SETUP", "LOW"
    # body sentences after setup, before reveal -> escalate over time
    if first_body_idx >= 0 and idx > first_body_idx:
        frac = (idx - first_body_idx) / max(total - first_body_idx, 1)
        return "ESCALATION", ("MEDIUM" if frac < 0.5 else "HIGH")
    return "SETUP", "LOW"


PURPOSE = {
    ("HOOK", "HIGH"): "arresting image under unresolved-question opening",
    ("SETUP", "LOW"): "establish world/characters calmly",
    ("ESCALATION", "MEDIUM"): "rising unease; introduce threat space",
    ("ESCALATION", "HIGH"): "dense cutting; danger closes in",
    ("REVEAL", "PEAK"): "climactic imagery under the twist",
    ("ENDING", "MEDIUM"): "consequence settling",
    ("PAYOFF", "PAYOFF"): "final narrative consequence, lingering close",
}

TRANSITION = {
    "LOW": "straight cut",
    "MEDIUM": "cut on sentence start",
    "HIGH": "hard cut on stress word",
    "PEAK": "hard cut + hold on reveal",
    "PAYOFF": "slow settle, no interrupt",
}


# ── Scene-cut detection ──────────────────────────────────────────

def detect_scene_cuts(source_path: Path, cache_dir: Optional[Path] = None,
                      threshold: float = 0.30, sample_fps: int = 8) -> List[float]:
    """Detect real shot boundaries. Returns sorted cut timestamps (sec).
    Cached by source size+mtime so repeated runs are instant."""
    src = Path(source_path)
    key = f"{src.stem}_{src.stat().st_size}_{int(src.stat().st_mtime)}.json"
    cache_file = (Path(cache_dir) / key) if cache_dir else None
    if cache_file and cache_file.exists():
        return json.loads(cache_file.read_text(encoding="utf-8"))

    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(src),
           "-vf", f"fps={sample_fps},scale=192:-2,"
                  f"select='gt(scene,{threshold})',metadata=print",
           "-an", "-f", "null", "-"]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    cuts = sorted({float(m.group(1)) for m in
                   re.finditer(r"pts_time:(\d+\.?\d*)", proc.stderr + proc.stdout)})
    if cache_file:
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_file.write_text(json.dumps(cuts), encoding="utf-8")
    return cuts


def shot_list(cuts: List[float], source_duration: float) -> List[Dict[str, float]]:
    """Convert cut timestamps into [start,end) shots covering the film."""
    bounds = [0.0] + [c for c in cuts if 0.5 < c < source_duration - 1.0] + [source_duration]
    return [{"start": bounds[i], "end": bounds[i + 1]}
            for i in range(len(bounds) - 1)]


# ── Beat construction ────────────────────────────────────────────

def build_narration_beats(caption_beats: List[Dict], vo_duration: float,
                          sentences: List[str]) -> List[Dict[str, Any]]:
    """Group caption beats into visual beats aligned to sentence boundaries."""
    # Map each caption chunk to its sentence index by cumulative char share
    sent_spans = []  # [(start_t, end_t)] per sentence, proportional in time
    total_chars = sum(len(s) for s in sentences) or 1
    t = 0.0
    for s in sentences:
        dur = vo_duration * len(s) / total_chars
        sent_spans.append((t, t + dur))
        t += dur

    first_body = next((i for i, s in enumerate(sentences)
                       if re.search(r"is a \d{4}", s)), 1)
    beats = []
    seen_reveal = False
    for i, (text, (b0, b1)) in enumerate(zip(sentences, sent_spans)):
        phase, inten = classify_sentence(text, i, len(sentences), first_body,
                                         seen_reveal=seen_reveal)
        if phase == "REVEAL":
            seen_reveal = True
        beats.append({
            "start": b0, "end": b1, "narration": text.strip(),
            "phase": phase, "intensity": inten,
            "purpose": PURPOSE.get((phase, inten), PURPOSE[("SETUP", "LOW")]),
            "transition": TRANSITION[inten],
        })
    # Normalize: stretch/compress spans to exactly match vo_duration
    if beats:
        scale = vo_duration / beats[-1]["end"]
        for b in beats:
            b["start"] *= scale
            b["end"] *= scale
    # Merge micro-beats (<1.2s) into previous to avoid strobe cuts
    merged = []
    for b in beats:
        if merged and (b["end"] - b["start"]) < 1.2:
            prev = merged[-1]
            same = prev["phase"] == b["phase"]
            prev["end"] = b["end"]
            prev["narration"] = prev["narration"] + " " + b["narration"]
            if not same:
                prev["phase"] = b["phase"]  # later phase wins the window
                prev["intensity"] = b["intensity"]
                prev["purpose"] = b["purpose"]
        else:
            merged.append(b)
    return merged


def select_source_shots(beat: Dict[str, Any], shots: List[Dict[str, float]],
                        used: set) -> List[Dict[str, float]]:
    """Pick real shot(s) filling this beat's window, respecting phase region
    and intensity-driven shot-length preference. Never reuse a shot."""
    lo_f, hi_f = PHASE_PRIORS[beat["phase"]]

    # region by fraction of max shot end
    max_end = max((s["end"] for s in shots), default=1.0) or 1.0
    region = [s for s in shots
              if lo_f * max_end <= s["start"] <= hi_f * max_end
              and (round(s["start"], 1), round(s["end"], 1)) not in used]
    pool = region or [s for s in shots
                      if (round(s["start"], 1), round(s["end"], 1)) not in used]
    if not pool:
        return []

    target = INTENSITY_TARGET_SHOT[beat["intensity"]]
    need = beat.get("duration", beat.get("end", 0) - beat.get("start", 0))

    picked = []
    remaining = need
    guard = 0
    while remaining > 0.3 and guard < 12:
        guard += 1
        # shot closest to min(target, remaining) preference
        want = min(target, remaining)
        best = min(pool, key=lambda s: abs((s["end"] - s["start"]) - want))
        key = (round(best["start"], 1), round(best["end"], 1))
        pool.remove(best)
        used.add(key)
        take = min(best["end"], best["start"] + remaining) - best["start"]
        if take <= 0.05:
            continue
        picked.append({"start": round(best["start"], 2),
                       "end": round(best["start"] + take, 2)})
        remaining -= take
    return picked


def build_visual_plan(vo_duration: float, sentences: List[str],
                      caption_beats: List[Dict], cuts: List[float],
                      source_duration: float) -> Dict[str, Any]:
    """Full beat map: narration beats + selected source shots."""
    beats = build_narration_beats(caption_beats, vo_duration, sentences)
    shots = shot_list(cuts, source_duration)
    used: set = set()

    # OPENING DESIGN: first beat capped at 2.5s from a dense-cut neighborhood.
    # Overflow time merges into beat[1] so the timeline stays gap-free.
    if beats and shots:
        cap = beats[0]["start"] + 2.5
        if beats[0]["end"] > cap and len(beats) > 1:
            beats[1]["start"] = cap
            beats[0]["end"] = cap
        elif beats[0]["end"] > cap:
            beats[0]["end"] = cap
        density = {}
        for i in range(2, len(shots)):
            span = shots[i]["end"] - shots[i - 2]["start"]
            density[i - 1] = 2 / span if span > 0 else 0
        hot_i = max(density, key=density.get)
        hot = shots[hot_i]
        used.add((round(hot["start"], 1), round(hot["end"], 1)))
        beats[0]["source_shots"] = [{
            "start": round(hot["start"], 2),
            "end": round(min(hot["end"],
                             hot["start"] + beats[0]["end"] - beats[0]["start"]), 2)}]
        beats[0]["purpose"] = "opening 2s: strongest-cut neighborhood, immediate hook"

    for b in beats:
        if b.get("source_shots"):
            continue
        b["source_shots"] = select_source_shots(b, shots, used)

    total_changes = sum(len(b["source_shots"]) for b in beats)
    return {
        "beats": beats,
        "segment_count": total_changes,
        "visual_change_every_sec": round(vo_duration / max(total_changes, 1), 2),
        "phases_present": list(dict.fromkeys(b["phase"] for b in beats)),
        "opening_beat_sec": round(
            beats[0]["source_shots"][0]["end"] - beats[0]["source_shots"][0]["start"], 2)
            if beats and beats[0]["source_shots"] else 0.0,
        "ending_phase_last": beats[-1]["phase"] if beats else "",
        "fallback_uniform": False,
    }


def build_uniform_fallback(vo_duration: float, n_seg: int = 7,
                           source_duration: float = 1.0) -> Dict[str, Any]:
    """Legacy plan shape for fallback parity."""
    seg = vo_duration / n_seg
    beats = []
    phases = ["HOOK", "SETUP", "ESCALATION", "REVEAL", "ENDING", "PAYOFF"]
    for i in range(n_seg):
        phase = phases[min(i * len(phases) // n_seg, len(phases) - 1)]
        center = (i + 0.5) / n_seg
        start = max(0.03, center - 0.04) * source_duration
        beats.append({"start": i * seg, "end": (i + 1) * seg,
                      "narration": "", "phase": phase, "intensity": "MEDIUM",
                      "purpose": "uniform split (fallback)",
                      "transition": "cut",
                      "source_shots": [{"start": round(start, 2),
                                        "end": round(start + seg + 0.2, 2)}]})
    return {"beats": beats, "segment_count": n_seg,
            "visual_change_every_sec": round(seg, 2),
            "phases_present": phases[:n_seg] if n_seg < 6 else phases,
            "opening_beat_sec": round(seg, 2),
            "ending_phase_last": "PAYOFF", "fallback_uniform": True}


# ── Rendering ────────────────────────────────────────────────────

def render_beat_segments(source_copy: Path, work: Path, plan: Dict[str, Any],
                         cut_vertical_segment_fn) -> List[str]:
    """Render every source shot of every beat as its own vertical segment."""
    files = []
    idx = 0
    for bi, beat in enumerate(plan["beats"]):
        for shot in beat["source_shots"]:
            name = f"seg_{idx:02d}.mp4"
            dur = shot["end"] - shot["start"]
            ok = cut_vertical_segment_fn(source_copy, work, name,
                                         shot["start"], dur + 0.15)
            if ok:
                files.append(name)
            idx += 1
    return files


# ── Validation (used by tests) ───────────────────────────────────

def validate_plan(plan: Dict[str, Any], vo_duration: float) -> List[str]:
    """Return list of violations; empty list == valid beat-aligned plan."""
    issues = []
    required_phases = ["HOOK", "SETUP", "ESCALATION", "REVEAL", "ENDING", "PAYOFF"]
    phases = plan["phases_present"]
    missing = [p for p in required_phases if p not in phases]
    if missing:
        issues.append(f"missing phases: {missing}")

    rate = plan["visual_change_every_sec"]
    if not (2.0 <= rate <= 5.5):
        issues.append(f"visual change every {rate}s outside 2-5.5s target")

    if plan["opening_beat_sec"] > 2.6:
        issues.append(f"opening beat {plan['opening_beat_sec']}s exceeds 2.5s design")

    beats = plan["beats"]
    t = 0.0
    for b in beats:
        if abs(b["start"] - t) > 0.35:
            issues.append(f"gap/overlap at beat starting {b['start']:.2f} (expected {t:.2f})")
        t = b["end"]
    if abs(t - vo_duration) > 0.5:
        issues.append(f"beats cover {t:.2f}s != vo {vo_duration:.2f}s")

    # Escalation invariant: REVEAL shots must come later in film than SETUP shots
    def avg_src(phase):
        vals = [s["start"] for b in beats if b["phase"] == phase
                for s in b["source_shots"]]
        return sum(vals) / len(vals) if vals else None
    setup_avg, reveal_avg = avg_src("SETUP"), avg_src("REVEAL")
    if setup_avg is not None and reveal_avg is not None and reveal_avg <= setup_avg:
        issues.append("escalation violated: REVEAL sourced earlier than SETUP")

    if plan["ending_phase_last"] != "PAYOFF":
        issues.append(f"last phase is {plan['ending_phase_last']}, must be PAYOFF")
    return issues
