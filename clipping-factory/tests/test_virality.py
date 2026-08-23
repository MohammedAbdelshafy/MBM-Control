"""Virality engine regression tests — deterministic scoring invariants."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clipping_factory.virality_engine import (
    analyze_artifact,
    band_for,
    generate_hook_variants,
    score_commentability,
    score_curiosity_gap,
    score_hook,
    score_payoff,
    select_best_hook,
)


def _artifact(name):
    p = Path(__file__).resolve().parents[1] / "artifacts" / "twistsrevealed" / name
    if not p.exists():
        import pytest
        pytest.skip(f"artifact missing: {name}")
    return p


# ── Scoring primitives ───────────────────────────────────────────

def test_score_hook_rejects_generic_openers():
    assert score_hook("Today we're talking about a classic movie.") <= 0.15
    assert score_hook("This movie is about a haunted house.") <= 0.15


def test_score_hook_rewards_contradiction_and_names():
    weak = score_hook("There was a house on a hill.")
    strong = score_hook("By sunrise, everyone in that house would be dead.")
    assert strong > weak


def test_band_boundaries():
    assert band_for(50) == "DO_NOT_POST"
    assert band_for(60) == "REWRITE"
    assert band_for(75) == "ACCEPTABLE"
    assert band_for(85) == "STRONG"
    assert band_for(95) == "PREMIUM"


def test_hook_generation_all_supported_by_research():
    variants = generate_hook_variants(
        "Test Movie", 1999,
        "A man traps intruders in his house. They cannot escape.",
        "The daughter was protecting them. He dies at dawn.",
        ["Anna", "The Man"])
    strategies = {v["strategy"] for v in variants}
    # DANGER must appear (death markers present); CONSEQUENCE always present
    assert "DANGER" in strategies
    assert "CONSEQUENCE" in strategies
    # Every variant carries its supporting evidence line
    for v in variants:
        assert v.get("supported_by"), f"hook without research support: {v}"


def test_select_best_hook_orders_by_score():
    variants = [
        {"strategy": "A", "hook": "Today we're talking about things.", "supported_by": "x"},
        {"strategy": "B", "hook": "By sunrise, Cesare would be dead.", "supported_by": "x"},
    ]
    best, scored = select_best_hook(variants)
    assert best["strategy"] == "B"
    assert scored[0]["hook_score"] >= scored[-1]["hook_score"]


def test_payoff_penalizes_generic_sting():
    generic = score_payoff(
        "He trusted her.", "The truth about X is something audiences never forget.", "")
    specific = score_payoff(
        "He trusted her.",
        "The sacrifice in Nosferatu is the kind of ending that stays with you long after the credits roll.",
        "Ellen sacrifices herself.")
    assert specific > generic


def test_commentability_zero_for_engagement_bait():
    assert score_commentability("Great movie! Comment YES if you agree!") == 0.0
    assert score_commentability("Would you have believed Francis?") >= 0.8


def test_curiosity_gap_rewards_withholding():
    early = score_curiosity_gap(
        "The story is revealed to be the delusion of Francis immediately. Then more plot happens here.")
    withheld = score_curiosity_gap(
        "They arrive at the fairground. But here's where everything changes. Nobody expected the final scene.")
    assert withheld > early


# ── Full artifact analysis ───────────────────────────────────────

REQUIRED_KEYS = {"score", "band", "recommendation", "weakest_dimension",
                 "best_hook", "recommended_fix", "dimensions_weighted",
                 "retention_map", "hook_variants", "title_variants"}


def test_analysis_nosferatu_in_acceptable_band():
    r = analyze_artifact(_artifact("20260823_180547_TR-1922-B02CE02259AB"))
    assert REQUIRED_KEYS <= set(r)
    assert 55 <= r["score"] <= 100
    assert r["score"] >= 70  # was measured 71
    assert r["band"] in ("ACCEPTABLE", "STRONG")


def test_analysis_caligari_before_below_after():
    before = analyze_artifact(_artifact("20260823_180100_TR-1920-A38FE1F94821"))
    after = analyze_artifact(_artifact("20260823_211005_IMPR_TR-1920-IMPROVED"))
    assert after["score"] > before["score"], \
        f"improvement run regressed: {before['score']} -> {after['score']}"


def test_no_analysis_returns_perfect_ten_equivalent():
    """No clip may score 100 — perfection is not credible."""
    for name in ("20260823_180100_TR-1920-A38FE1F94821",
                 "20260823_180547_TR-1922-B02CE02259AB",
                 "20260823_211005_IMPR_TR-1920-IMPROVED"):
        p = Path(__file__).resolve().parents[1] / "artifacts" / "twistsrevealed" / name
        if not p.exists():
            continue
        r = analyze_artifact(p)
        assert r["score"] < 100, f"{name} suspiciously perfect"
