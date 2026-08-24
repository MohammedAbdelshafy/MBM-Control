"""Beat-aligned visual engine tests — deterministic, no ffmpeg/network."""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clipping_factory.beat_visual_engine import (
    build_narration_beats,
    build_uniform_fallback,
    build_visual_plan,
    classify_sentence,
    select_source_shots,
    shot_list,
    validate_plan,
)


def _synthetic_cuts(source_dur=4800.0, every=9.0):
    """Uniform-ish cut grid with jitter — deterministic."""
    cuts = []
    t = every
    i = 0
    while t < source_dur - 5:
        cuts.append(round(t + (i % 3), 2))
        t += every + (i % 4)
        i += 1
    return cuts


SENTENCES = [
    "By the end of this night, Count Orlok would be dead.",          # HOOK
    "Nosferatu is a 1922 horror and supernatural, directed by F. W. Murnau.",  # SETUP
    "An estate agent travels to the Carpathians to close a property deal.",     # SETUP/ESC
    "The tension between Thomas Hutter and Count Orlok drives the entire story.",  # ESCALATION
    "But here's where everything changes.",                          # REVEAL marker
    "Ellen reads the vampire lore: a sinless woman must willingly give her blood.",  # REVEAL
    "She sacrifices herself, and Orlok vanishes into smoke and dust.",  # REVEAL
    "Would you have believed Thomas Hutter?",                        # PAYOFF question
]


def _vo_duration_for(sentences, wpm=150):
    words = sum(len(s.split()) for s in sentences)
    return words / wpm * 60


def _make_plan():
    dur = _vo_duration_for(SENTENCES)
    cuts = _synthetic_cuts()
    plan = build_visual_plan(dur, SENTENCES, [], cuts=cuts, source_duration=4800.0)
    return plan, dur


def test_beat_alignment_covers_full_duration_without_gaps():
    plan, dur = _make_plan()
    issues = validate_plan(plan, dur)
    gap_issues = [i for i in issues if "gap/overlap" in i or "beats cover" in i]
    assert not gap_issues, gap_issues


def test_required_phases_present_in_order():
    plan, dur = _make_plan()
    issues = validate_plan(plan, dur)
    missing = [i for i in issues if "missing phases" in i or "last phase" in i]
    assert not missing, (issues, plan["phases_present"])


def test_visual_change_rate_within_target_band():
    plan, dur = _make_plan()
    assert 2.0 <= plan["visual_change_every_sec"] <= 5.5, plan["visual_change_every_sec"]
    assert plan["segment_count"] >= math.ceil(dur / 5.5)


def test_opening_beat_is_short_and_purposeful():
    plan, dur = _make_plan()
    assert plan["opening_beat_sec"] <= 2.6
    first = plan["beats"][0]
    assert first["phase"] == "HOOK"
    assert "opening" in first["purpose"].lower()


def test_escalation_invariant_reveal_after_setup_in_source():
    plan, dur = _make_plan()
    issues = validate_plan(plan, dur)
    esc = [i for i in issues if "escalation violated" in i]
    assert not esc, issues


def test_no_shot_reuse_across_beats():
    plan, dur = _make_plan()
    seen = set()
    for b in plan["beats"]:
        for s in b["source_shots"]:
            key = (round(s["start"], 1), round(s["end"], 1))
            assert key not in seen, f"shot reused: {key}"
            seen.add(key)


def test_intensity_mapping_rises_to_peak_at_reveal():
    plan, dur = _make_plan()
    intensities = [b["intensity"] for b in plan["beats"]]
    peak_pos = intensities.index("PEAK") if "PEAK" in intensities else None
    low_pos = intensities.index("LOW") if "LOW" in intensities else None
    assert peak_pos is not None and low_pos is not None
    assert low_pos < peak_pos


def test_generalizes_to_second_movie():
    """NotLD-style data must produce a valid plan — no Nosferatu hard-coding."""
    sentences = [
        "Something happened to Ben that defies explanation.",
        "Night of the Living Dead is a 1968 horror directed by George A. Romero.",
        "The tension between Ben and Barbra drives the entire story.",
        "But here's where everything changes.",
        "Ben survives the night but is shot by a posse.",
        "Did Ben ever stand a chance?",
    ]
    dur = _vo_duration_for(sentences)
    plan = build_visual_plan(dur, sentences, [], cuts=_synthetic_cuts(),
                             source_duration=5600.0)
    issues = [i for i in validate_plan(plan, dur) if "escalation" in i or "phases" in i]
    assert not issues


def test_fallback_uniform_plan_still_valid_shape():
    fb = build_uniform_fallback(48.0, n_seg=7, source_duration=4800.0)
    assert fb["fallback_uniform"] is True
    assert len(fb["beats"]) == 7
    issues = validate_plan(fb, 48.0)
    # fallback may miss fine-grained phases but must cover duration cleanly
    assert not any("beats cover" in i for i in issues)


def test_select_source_shots_never_returns_empty_for_reasonable_region():
    cuts = _synthetic_cuts()
    shots = shot_list(cuts, 4800.0)
    beat = {"phase": "REVEAL", "intensity": "PEAK", "duration": 3.0}
    used = set()
    picked = select_source_shots(beat, shots, used)
    assert picked, "no shots selected"
    total = sum(s["end"] - s["start"] for s in picked)
    assert abs(total - beat["duration"]) < 0.6


def test_classify_sentence_hook_and_payoff():
    phase, inten = classify_sentence(SENTENCES[0], 0, 8, 1)
    assert phase == "HOOK" and inten == "HIGH"
    q = "Would you have believed Thomas Hutter?"
    phase, inten = classify_sentence(q, 7, 8, 1)
    assert phase == "PAYOFF"
