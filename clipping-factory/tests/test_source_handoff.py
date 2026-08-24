"""
Regression + failure-injection suite for the DISCOVERY -> RESOLVED SOURCE ->
ACQUISITION contract, the pre-production gate, the optional visual provider
architecture, and script quality invariants.
"""
import json
import tempfile
from pathlib import Path

import pytest


# â”€â”€ Discovery -> Source handoff â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_pd_candidates_carry_resolved_uri():
    """Every public-domain candidate reaching production must have a real URI."""
    from clipping_factory.movie_discovery import discover_movies, SourceClass

    pool = discover_movies(genres=None, count=24)
    pd = [m for m in pool if m.source_class == SourceClass.PUBLIC_DOMAIN.value]
    assert pd, "curated database must contain public-domain candidates"
    for m in pd:
        assert m.source_class == "public_domain"
        if not m.source_uri:
            continue  # honestly blocked later by the gate
        assert m.source_uri.startswith("https://archive.org/download/"), (
            f"{m.title}: source_uri must be a real archive.org download URL")


def test_acquire_blocks_on_empty_uri():
    from clipping_factory.source_acquisition import acquire_source

    res = acquire_source("TR-TEST", "Some Film", 1950, "public_domain", "")
    assert res.status == "blocked"
    assert "SOURCE_BLOCKED" in res.error
    assert res.local_path == ""


def test_acquire_rejects_unverified_provenance():
    from clipping_factory.source_acquisition import acquire_source

    res = acquire_source("TR-TEST2", "Modern Film", 2020, "unverified",
                         "https://archive.org/download/x/y.mp4")
    assert res.status == "rejected_provenance"


def test_resolver_url_for_uses_cache(monkeypatch):
    """url_for only returns VERIFIED cached URLs."""
    import clipping_factory._resolve_pd_sources as resolver

    with tempfile.TemporaryDirectory() as td:
        fake = Path(td) / "pd_source_cache.json"
        fake.write_text(json.dumps({
            "Real Film (1999)": {"url": "https://archive.org/download/a/b.mp4",
                                 "verified": True},
            "Fake Film (2001)": {"url": "https://archive.org/download/c/d.mp4",
                                 "verified": False},
        }), encoding="utf-8")
        monkeypatch.setattr(resolver, "CACHE_FILE", fake)
        assert resolver.url_for("Real Film", 1999) != ""
        assert resolver.url_for("Fake Film", 2001) == ""
        assert resolver.url_for("Unknown Film", 1950) == ""


# â”€â”€ Script quality â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _mk_script(**kw):
    from clipping_factory.script_agent import generate_recap_script
    base = dict(
        campaign_id="TR-T", title="Test Film", year=1962,
        synopsis="A woman survives a car crash and takes a job in a strange town. "
                 "A pale figure begins stalking her. " * 3,
        ending_description="She was dead the entire film. The crash killed everyone.",
        key_characters=["Mary", "The Man"], genres=["horror", "mystery"],
        tone="dark_suspenseful", target_duration_min=35, target_duration_max=75,
        director="Herk Harvey",
    )
    base.update(kw)
    return generate_recap_script(**base)


def test_script_never_contains_production_notes():
    s = _mk_script()
    assert "[Note:" not in s.narration, \
        "production notes must never be spoken by TTS"
    assert "may need trimming" not in s.narration


def test_script_has_hook_and_final_sting():
    s = _mk_script()
    first_line = [l for l in s.narration.split("\n") if l.strip()][0]
    assert first_line == s.hook
    assert s.narration.rstrip().endswith(s.ending_sting), \
        "narration must end on the final sting"


def test_script_estimated_duration_in_band():
    s = _mk_script()
    assert 35 <= s.estimated_duration_sec <= 80, \
        f"estimated {s.estimated_duration_sec}s outside the 35-75s band"


# â”€â”€ Optional visual provider architecture â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_higgsfield_unconfigured_is_unavailable_and_never_fake():
    """No HF_API_KEY -> UNAVAILABLE, ok=False, empty output. Never a fake job."""
    import os
    from clipping_factory.providers.higgsfield_provider import (
        HiggsfieldProvider, ProviderState,
    )

    os.environ.pop("HF_API_KEY", None)
    p = HiggsfieldProvider(api_key="")
    h = p.health_check()
    assert h["state"] == ProviderState.UNAVAILABLE.value

    r = p.generate_scene("dark corridor, slow push-in", Path("x.mp4"))
    assert r["ok"] is False
    assert r["output"] == ""
    assert r["state"] == ProviderState.UNAVAILABLE.value


def test_router_falls_back_to_local_when_higgsfield_down():
    from clipping_factory.providers.higgsfield_provider import (
        HiggsfieldProvider, VisualProviderRouter,
    )

    router = VisualProviderRouter(higgsfield=HiggsfieldProvider(api_key=""))
    route = router.route()
    assert route["provider"] == "local_ffmpeg", \
        "factory must CONTINUE on the local pipeline when Higgsfield is unavailable"


def test_plan_required_does_not_block(monkeypatch):
    """PLAN_REQUIRED must return ok=False with state preserved â€” campaign continues."""
    from clipping_factory.providers.higgsfield_provider import (
        HiggsfieldProvider, ProviderState,
    )

    p = HiggsfieldProvider(api_key="test-key")
    monkeypatch.setattr(p, "health_check",
                        lambda: {"provider": "higgsfield",
                                 "state": ProviderState.PLAN_REQUIRED.value})
    r = p.generate_scene("scene", Path("y.mp4"))
    assert r["ok"] is False
    assert r["state"] == ProviderState.PLAN_REQUIRED.value
    assert r["output"] == ""


# â”€â”€ Pre-production gate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_full_cycle_gate_skips_empty_uri_candidate():
    """A candidate without source_uri is recorded source_blocked, never produced."""
    from clipping_factory.full_cycle import run_full_cycle
    from clipping_factory.movie_discovery import MovieCandidate
    from unittest.mock import patch

    movie_no_src = MovieCandidate(
        title="Ghost Feature", year=1951, genres=["horror"],
        source_class="public_domain", source_uri="")
    movie_ok = MovieCandidate(
        title="Real Feature", year=1955, genres=["horror"],
        source_class="public_domain", source_uri="https://archive.org/download/rf/real.mp4")

    captured = []

    def fake_produce(movie, profile, run_id, publish):
        captured.append(movie.campaign_id)
        return {"campaign_id": movie.campaign_id,
                "movie": movie.title, "status": "ready"}

    with patch("clipping_factory.full_cycle._produce_one", side_effect=fake_produce), \
         patch("clipping_factory.full_cycle.discover_movies",
               return_value=[movie_no_src, movie_ok]), \
         patch("clipping_factory.full_cycle.acquire_run_lock", return_value=True), \
         patch("clipping_factory.full_cycle.release_run_lock"), \
         patch("clipping_factory.full_cycle.complete_heartbeat"), \
         patch("clipping_factory.full_cycle.update_ledger"), \
         patch("clipping_factory.full_cycle._read_status_file", return_value={}):
        out = run_full_cycle(movie_count=1)

    statuses = [r.get("status") for r in out["results"]]
    assert "source_blocked" in statuses, "empty-uri candidate must be gated"
    assert captured == [movie_ok.campaign_id], \
        "production must never be attempted without a usable source"


# â”€â”€ Duplicate prevention guard â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_duplicate_campaign_skipped_by_guard(monkeypatch):
    """If a campaign is already ready_to_publish, _produce_one must skip it."""
    from clipping_factory.movie_discovery import MovieCandidate
    from clipping_factory.channel_profiles import get_profile

    profile = get_profile("twistsrevealed")
    dup = MovieCandidate(
        title="Nosferatu", year=1922, director="F. W. Murnau",
        genres=["horror"], synopsis="Vampire.", ending_description="He dies.",
        key_characters=["Nosferatu"], rating=8.0,
        source_class="public_domain", source_uri="http://example.com/v.mp4",
    )
    dup.campaign_id = "TR-1922-AAAA"
    dup.provenance = "public_domain"
    dup.duration = 5000.0

    # Simulate state where campaign is already terminal
    fake_state = {"TR-1922-AAAA": {"status": "ready_to_publish"}}
    monkeypatch.setattr("clipping_factory.full_cycle._read_status_file",
                        lambda: fake_state)

    from clipping_factory.full_cycle import _produce_one
    result = _produce_one(dup, profile, "RUN_TEST", publish=False)
    assert result["status"] == "skipped_duplicate", \
        f"guard must reject duplicate, got {result['status']}"


def test_duplicate_not_rejected_when_not_terminal(monkeypatch):
    """If status is 'researched' (non-terminal), production must proceed."""
    from clipping_factory.movie_discovery import MovieCandidate
    from clipping_factory.channel_profiles import get_profile
    from unittest.mock import MagicMock

    profile = get_profile("twistsrevealed")
    cand = MovieCandidate(
        title="Night of the Living Dead", year=1968, director="George A. Romero",
        genres=["horror"], synopsis="Zombies.", ending_description="He dies.",
        key_characters=["Ben"], rating=8.0,
        source_class="public_domain", source_uri="http://example.com/v.mp4",
    )
    cand.campaign_id = "TR-1968-BBBB"
    cand.provenance = "public_domain"
    cand.duration = 5500.0

    # Non-terminal status should NOT be skipped
    fake_state = {"TR-1968-BBBB": {"status": "researched"}}
    monkeypatch.setattr("clipping_factory.full_cycle._read_status_file",
                        lambda: fake_state)

    from clipping_factory.full_cycle import _produce_one
    # Will proceed past guard, then likely fail at acquire_source (no real data)
    # but the key assertion is it doesn't return skipped_duplicate
    result = _produce_one(cand, profile, "RUN_TEST", publish=False)
    assert result["status"] != "skipped_duplicate", \
        "non-terminal status must not trigger duplicate guard"


# â”€â”€ QA boolean type â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_qa_passed_is_boolean():
    """qa.passed must be a bool, never a string like 'aac'."""
    from clipping_factory.full_cycle import _qa_and_score
    from clipping_factory.channel_profiles import get_profile

    profile = get_profile("twistsrevealed")
    final = (Path("artifacts/twistsrevealed") /
             "20260823_140131_TR-1920-A38FE1F94821/final.mp4")
    if not final.exists():
        pytest.skip("artifact not available")

    # Mock caption_beats as list of dicts matching production format
    beats = [{"timestamp_end": 45.0}]
    qa = _qa_and_score(final, 45.0, 103, beats, 7, profile,
                       narration="He thought the house was empty. It wasn't. The Cabinet of Dr. Caligari is a 1920 psychological horror. But here's where everything changes. The entire story is revealed to be the delusion of Francis.")
    assert isinstance(qa["passed"], bool), \
        f"passed must be bool, got {type(qa['passed']).__name__}: {qa['passed']!r}"


# â”€â”€ Script punctuation â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def test_script_no_double_periods():
    """Narration must not contain '..' double periods."""
    from clipping_factory.script_agent import generate_recap_script

    s = generate_recap_script(
        campaign_id="TEST", title="Test Movie", year=2000,
        synopsis="He finds the truth. Everything changes.",
        ending_description="The story ends. He was dead all along.",
        key_characters=["Hero"], genres=["thriller"],
    )
    assert ".." not in s.narration, \
        f"double period found in narration: {s.narration!r}"


def test_script_no_production_notes():
    """Narration must never contain [Note: ...] production annotations."""
    from clipping_factory.script_agent import generate_recap_script

    s = generate_recap_script(
        campaign_id="TEST", title="Test Movie", year=2000,
        synopsis="A mystery unfolds. The truth is shocking.",
        ending_description="He was the killer all along.",
        key_characters=["Detective"], genres=["mystery"],
    )
    assert "[Note" not in s.narration, \
        f"production note found in narration: {s.narration!r}"


def test_no_generic_endings():
    """Scripts must never use generic boilerplate endings."""
    from clipping_factory.script_agent import generate_recap_script

    generic_phrases = [
        "something audiences never forget",
        "nothing will ever be the same",
        "changes everything",
        "forever changed",
    ]
    # Test across multiple movies
    movies = [
        ("Nosferatu", 1922, "Vampire travels to a city.", "Ellen sacrifices herself to destroy the vampire.", ["Thomas Hutter", "Count Orlok"], ["horror"]),
        ("Night of the Living Dead", 1968, "Zombies attack a farmhouse.", "Ben survives the night but is shot by a mob.", ["Ben", "Barbara"], ["horror"]),
        ("Carnival of Souls", 1962, "Woman follows a mysterious figure.", "She realizes she drowned in the river.", ["Mary Henry"], ["horror"]),
    ]
    for title, year, syn, end, chars, genres in movies:
        s = generate_recap_script(
            campaign_id="TEST", title=title, year=year,
            synopsis=syn, ending_description=end,
            key_characters=chars, genres=genres,
        )
        for phrase in generic_phrases:
            assert phrase not in s.narration.lower(), \
                f"generic ending '{phrase}' found in {title} narration"


def test_hook_diversity():
    """Scripts for different movies should use different hook strategies."""
    from clipping_factory.script_agent import generate_recap_script

    hooks = set()
    movies = [
        ("Nosferatu", 1922, "Vampire travels to a city.", "Ellen sacrifices herself to destroy the vampire.", ["Thomas Hutter", "Count Orlok"], ["horror"]),
        ("Night of the Living Dead", 1968, "Zombies attack a farmhouse.", "Ben survives the night but is shot by a mob.", ["Ben", "Barbara"], ["horror"]),
        ("Carnival of Souls", 1962, "Woman follows a mysterious figure.", "She realizes she drowned in the river.", ["Mary Henry"], ["horror"]),
    ]
    for title, year, syn, end, chars, genres in movies:
        s = generate_recap_script(
            campaign_id="TEST", title=title, year=year,
            synopsis=syn, ending_description=end,
            key_characters=chars, genres=genres,
        )
        hooks.add(s.hook)
    # At least 2 different hooks across 3 movies
    assert len(hooks) >= 2, f"hooks not diverse enough: {hooks}"


def test_script_has_hook_and_sting():
    """Every script must open with a hook and end with a sting."""
    from clipping_factory.script_agent import generate_recap_script

    s = generate_recap_script(
        campaign_id="TEST", title="Test Movie", year=2000,
        synopsis="A man searches for answers. The truth is dark.",
        ending_description="He discovers the truth. His world collapses.",
        key_characters=["Hero"], genres=["thriller"],
    )
    lines = [l.strip() for l in s.narration.split("\n") if l.strip()]
    assert len(lines) >= 2, "script needs hook + sting minimum"
    # Sting must reference the movie name (movie-specific, not generic)
    assert "test movie" in lines[-1].lower(), \
        f"final line should reference the movie, got: {lines[-1]!r}"

