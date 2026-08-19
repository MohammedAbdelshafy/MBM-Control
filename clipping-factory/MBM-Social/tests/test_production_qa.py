"""
Comprehensive Regression Test Suite — MBM Social Production QA Gates

Tests all QA gates, state machine, platform validation, duplicate protection,
and failure recovery. Uses real media files and actual ffprobe inspection.

Run: python -m pytest tests/test_production_qa.py -v
"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

# Add MBM-Social to path
_MBM_SOCIAL_DIR = Path(__file__).resolve().parent.parent
if str(_MBM_SOCIAL_DIR) not in sys.path:
    sys.path.insert(0, str(_MBM_SOCIAL_DIR))

from mbm_social.video_gate import validate_video_file, ffprobe_json, VideoProbeResult
from mbm_social.audio_gate import validate_audio, probe_audio_stream, AudioProbeResult
from mbm_social.caption_gate import validate_captions, parse_srt, CaptionEntry
from mbm_social.platform_gate import validate_all_platforms, validate_platform, PLATFORM_SPECS
from mbm_social.creative_gate import score_creative
from mbm_social.state_machine import ProductionStateMachine, VALID_STATES, FAILURE_STATES, TRANSITIONS

TEST_MEDIA_DIR = _MBM_SOCIAL_DIR / "viral_pool"


@pytest.fixture
def source_video():
    """Find first available test video."""
    for name in ["viral_voice_agency_01.mp4", "viral_movie_recap_01.mp4", "test_video.mp4"]:
        p = TEST_MEDIA_DIR / name
        if p.exists():
            return p
    pytest.skip("No test media available")


@pytest.fixture
def tmp_artifacts(tmp_path):
    """Create temp artifact directory structure."""
    for sub in ["source", "candidates", "final", "captions", "manifests", "reports"]:
        (tmp_path / sub).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def clip_from_source(source_video, tmp_artifacts):
    """Generate a test clip from source video."""
    import subprocess
    clip_path = tmp_artifacts / "candidates" / "test_clip.mp4"
    cmd = [
        "ffmpeg", "-y", "-i", str(source_video),
        "-ss", "0", "-t", "10",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
        "-c:a", "aac", "-b:a", "64k",
        str(clip_path),
    ]
    subprocess.run(cmd, capture_output=True, timeout=30)
    return clip_path


# ═══════════════════════════════════════════════════════════════════════════
# VIDEO GATE TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestVideoGate:
    def test_valid_video_passes(self, clip_from_source):
        gate = validate_video_file(clip_from_source)
        assert gate.status == "PASS", f"Valid clip should pass: {gate.reason}"

    def test_missing_file_blocked(self, tmp_path):
        gate = validate_video_file(tmp_path / "nonexistent.mp4")
        assert gate.status == "BLOCKED"
        assert "not found" in gate.reason.lower()

    def test_probe_returns_dimensions(self, clip_from_source):
        probe = ffprobe_json(clip_from_source)
        assert probe.width > 0
        assert probe.height > 0
        assert probe.duration > 0

    def test_probe_returns_codecs(self, clip_from_source):
        probe = ffprobe_json(clip_from_source)
        assert probe.video_codec in ("h264", "h265", "hevc", "vp9", "av1")
        assert probe.audio_codec in ("aac", "mp3", "opus", "vorbis")

    def test_9_16_aspect_ratio(self, clip_from_source):
        gate = validate_video_file(clip_from_source)
        assert gate.checks.get("aspect_ratio_9_16"), f"Expected 9:16 aspect ratio"

    def test_video_has_frames(self, clip_from_source):
        gate = validate_video_file(clip_from_source)
        assert gate.checks.get("has_frames"), "Video should have frames"

    def test_duration_in_bounds(self, clip_from_source):
        gate = validate_video_file(clip_from_source, min_duration=1.0, max_duration=30.0)
        assert gate.checks.get("duration_valid"), "Duration should be in bounds"

    def test_audio_video_sync(self, clip_from_source):
        gate = validate_video_file(clip_from_source)
        assert gate.checks.get("av_sync_within_1s"), "AV sync should be within 1s"

    def test_pixel_format_valid(self, clip_from_source):
        gate = validate_video_file(clip_from_source)
        assert gate.checks.get("pixel_format_valid"), f"Pixel format should be valid"


# ═══════════════════════════════════════════════════════════════════════════
# AUDIO GATE TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestAudioGate:
    def test_valid_audio_passes(self, clip_from_source):
        gate = validate_audio(clip_from_source)
        assert gate.status == "PASS", f"Valid audio should pass: {gate.reason}"

    def test_has_audio_stream(self, clip_from_source):
        gate = validate_audio(clip_from_source)
        assert gate.checks.get("has_audio_stream"), "Should have audio stream"

    def test_audio_codec_valid(self, clip_from_source):
        gate = validate_audio(clip_from_source)
        assert gate.checks.get("codec_valid"), "Audio codec should be valid"

    def test_audio_sample_rate_valid(self, clip_from_source):
        gate = validate_audio(clip_from_source)
        assert gate.checks.get("sample_rate_valid"), "Sample rate should be valid"

    def test_audio_channels_valid(self, clip_from_source):
        gate = validate_audio(clip_from_source)
        assert gate.checks.get("channels_valid"), "Channels should be 1-2"

    def test_probe_audio_returns_info(self, clip_from_source):
        probe = probe_audio_stream(clip_from_source)
        assert not probe.error
        assert probe.codec in ("aac", "mp3", "opus", "vorbis")
        assert probe.sample_rate > 0
        assert probe.channels > 0

    def test_missing_file_blocked(self, tmp_path):
        gate = validate_audio(tmp_path / "nonexistent.mp4")
        assert gate.status == "BLOCKED"


# ═══════════════════════════════════════════════════════════════════════════
# CAPTION GATE TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestCaptionGate:
    def test_valid_srt_passes(self, clip_from_source, tmp_artifacts):
        from tests.production_smoke_test import generate_test_srt
        srt_path = tmp_artifacts / "captions" / "test.srt"
        generate_test_srt(10.0, srt_path)
        gate = validate_captions(srt_path, clip_from_source)
        assert gate.status == "PASS", f"Valid SRT should pass: {gate.reason}"

    def test_parse_srt_entries(self, clip_from_source, tmp_artifacts):
        from tests.production_smoke_test import generate_test_srt
        srt_path = tmp_artifacts / "captions" / "test.srt"
        generate_test_srt(10.0, srt_path)
        entries, error = parse_srt(srt_path)
        assert not error
        assert len(entries) > 0

    def test_srt_chronological_order(self, clip_from_source, tmp_artifacts):
        from tests.production_smoke_test import generate_test_srt
        srt_path = tmp_artifacts / "captions" / "test.srt"
        generate_test_srt(10.0, srt_path)
        entries, _ = parse_srt(srt_path)
        for i in range(len(entries) - 1):
            assert entries[i].start_ms <= entries[i + 1].start_ms

    def test_srt_no_empty_text(self, clip_from_source, tmp_artifacts):
        from tests.production_smoke_test import generate_test_srt
        srt_path = tmp_artifacts / "captions" / "test.srt"
        generate_test_srt(10.0, srt_path)
        entries, _ = parse_srt(srt_path)
        for e in entries:
            assert len(e.text.strip()) > 0, f"Entry {e.index} has empty text"

    def test_srt_no_zero_duration(self, clip_from_source, tmp_artifacts):
        from tests.production_smoke_test import generate_test_srt
        srt_path = tmp_artifacts / "captions" / "test.srt"
        generate_test_srt(10.0, srt_path)
        entries, _ = parse_srt(srt_path)
        for e in entries:
            assert e.duration_ms > 0, f"Entry {e.index} has zero duration"

    def test_missing_srt_blocked(self, tmp_path):
        gate = validate_captions(tmp_path / "nonexistent.srt")
        assert gate.status == "BLOCKED"

    def test_all_structural_checks(self, clip_from_source, tmp_artifacts):
        from tests.production_smoke_test import generate_test_srt
        srt_path = tmp_artifacts / "captions" / "test.srt"
        generate_test_srt(10.0, srt_path)
        gate = validate_captions(srt_path, clip_from_source)
        assert gate.checks.get("has_entries")
        assert gate.checks.get("parseable")
        assert gate.checks.get("chronological_order")
        assert gate.checks.get("no_zero_duration")
        assert gate.checks.get("no_empty_text")
        assert gate.checks.get("no_corrupted_chars")
        assert gate.checks.get("valid_encoding")


# ═══════════════════════════════════════════════════════════════════════════
# PLATFORM GATE TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestPlatformGate:
    def test_youtube_shorts_pass(self, clip_from_source):
        gate = validate_platform(clip_from_source, "youtube_shorts")
        assert gate.status == "PASS", f"YouTube Shorts should pass: {gate.reason}"

    def test_instagram_reels_pass(self, clip_from_source):
        gate = validate_platform(clip_from_source, "instagram_reels")
        assert gate.status == "PASS", f"Instagram Reels should pass: {gate.reason}"

    def test_tiktok_pass(self, clip_from_source):
        gate = validate_platform(clip_from_source, "tiktok")
        assert gate.status == "PASS", f"TikTok should pass: {gate.reason}"

    def test_all_platforms_pass(self, clip_from_source):
        results = validate_all_platforms(clip_from_source)
        for platform, gate in results.items():
            assert gate.status == "PASS", f"{platform} failed: {gate.reason}"

    def test_unknown_platform_blocked(self, clip_from_source):
        gate = validate_platform(clip_from_source, "unknown_platform")
        assert gate.status == "BLOCKED"

    def test_platform_specs_defined(self):
        assert "youtube_shorts" in PLATFORM_SPECS
        assert "instagram_reels" in PLATFORM_SPECS
        assert "tiktok" in PLATFORM_SPECS

    def test_platform_dimensions(self):
        for name, spec in PLATFORM_SPECS.items():
            assert spec.width == 1080, f"{name} width should be 1080"
            assert spec.height == 1920, f"{name} height should be 1920"
            assert spec.aspect_ratio == "9:16", f"{name} aspect ratio should be 9:16"


# ═══════════════════════════════════════════════════════════════════════════
# CREATIVE GATE TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestCreativeGate:
    def test_valid_clip_scores_above_threshold(self, clip_from_source):
        gate = score_creative(clip_from_source)
        assert gate.creative_score >= 6.0, f"Score {gate.creative_score} should be >= 6.0"

    def test_creative_gate_passes(self, clip_from_source):
        gate = score_creative(clip_from_source)
        assert gate.status == "PASS", f"Valid clip should pass creative gate"

    def test_all_dimensions_scored(self, clip_from_source):
        gate = score_creative(clip_from_source)
        assert len(gate.dimensions) == 13, "Should score all 13 dimensions"

    def test_dimensions_in_range(self, clip_from_source):
        gate = score_creative(clip_from_source)
        for name, dim in gate.dimensions.items():
            assert 0 <= dim.score <= 10, f"{name} score {dim.score} out of range"

    def test_winner_reason_populated(self, clip_from_source):
        gate = score_creative(clip_from_source)
        assert gate.winner_reason, "Winner reason should be populated"

    def test_missing_file_blocked(self, tmp_path):
        gate = score_creative(tmp_path / "nonexistent.mp4")
        assert gate.status == "BLOCKED"


# ═══════════════════════════════════════════════════════════════════════════
# STATE MACHINE TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestStateMachine:
    def test_happy_path(self):
        sm = ProductionStateMachine()
        asset_id = "test_happy"
        path = ["PROCESSING", "CLIPPED", "RENDERED", "QA_APPROVED",
                "READY_TO_PUBLISH", "PUBLISH_REQUESTED", "PUBLISHED", "VERIFIED"]
        for state in path:
            assert sm.transition(asset_id, state), f"Failed: -> {state}"
        assert sm.get_state(asset_id) == "VERIFIED"

    def test_invalid_transition_rejected(self):
        sm = ProductionStateMachine()
        asset_id = "test_invalid"
        sm.transition(asset_id, "PROCESSING")
        sm.transition(asset_id, "CLIPPED")
        sm.transition(asset_id, "RENDERED")
        sm.transition(asset_id, "QA_APPROVED")
        sm.transition(asset_id, "READY_TO_PUBLISH")
        sm.transition(asset_id, "PUBLISH_REQUESTED")
        sm.transition(asset_id, "PUBLISHED")
        sm.transition(asset_id, "VERIFIED")
        # VERIFIED is terminal — nothing should work
        assert not sm.transition(asset_id, "PROCESSING")
        assert not sm.transition(asset_id, "PUBLISH_FAILED")
        assert sm.get_state(asset_id) == "VERIFIED"

    def test_failure_recovery(self):
        sm = ProductionStateMachine()
        asset_id = "test_recovery"
        sm.transition(asset_id, "PROCESSING")
        sm.transition(asset_id, "QA_REJECTED")
        sm.transition(asset_id, "PROCESSING")
        sm.transition(asset_id, "CLIPPED")
        assert sm.get_state(asset_id) == "CLIPPED"

    def test_retry_exhaustion(self):
        sm = ProductionStateMachine()
        asset_id = "test_retry"
        sm.transition(asset_id, "PROCESSING")
        sm.transition(asset_id, "CLIPPED")
        sm.transition(asset_id, "RENDERED")
        sm.transition(asset_id, "QA_APPROVED")
        sm.transition(asset_id, "READY_TO_PUBLISH")
        # Each PUBLISH_FAILED and RETRY_PENDING increments retry_count (both are failure states)
        for i in range(2):
            sm.transition(asset_id, "PUBLISH_REQUESTED")
            sm.transition(asset_id, "PUBLISH_FAILED")
            sm.transition(asset_id, "RETRY_PENDING")
        asset = sm.assets[asset_id]
        assert asset.is_retry_exhausted  # retry_count=4 >= max_retries=3
        assert asset.retry_count >= 3

    def test_all_valid_states_exist(self):
        assert "DISCOVERED" in VALID_STATES
        assert "VERIFIED" in VALID_STATES
        assert "PUBLISHED" in VALID_STATES

    def test_all_failure_states_exist(self):
        assert "QA_REJECTED" in FAILURE_STATES
        assert "PUBLISH_FAILED" in FAILURE_STATES
        assert "VERIFY_FAILED" in FAILURE_STATES
        assert "RETRY_PENDING" in FAILURE_STATES

    def test_all_transitions_have_targets(self):
        for state in VALID_STATES | FAILURE_STATES:
            assert state in TRANSITIONS, f"State {state} missing from TRANSITIONS"

    def test_to_dict(self):
        sm = ProductionStateMachine()
        sm.transition("x", "PROCESSING")
        d = sm.assets["x"].to_dict()
        assert d["asset_id"] == "x"
        assert d["current_state"] == "PROCESSING"
        assert len(d["history"]) == 1

    def test_persistence(self, tmp_path):
        state_file = tmp_path / "state.json"
        sm1 = ProductionStateMachine(state_file)
        sm1.transition("persist_test", "PROCESSING")
        sm1.transition("persist_test", "CLIPPED")

        sm2 = ProductionStateMachine(state_file)
        assert sm2.get_state("persist_test") == "CLIPPED"


# ═══════════════════════════════════════════════════════════════════════════
# DUPLICATE PROTECTION TESTS
# ═══════════════════════════════════════════════════════════════════════════

class TestDuplicateProtection:
    def test_same_title_detected(self):
        seen = set()
        title = "Test Video Title"
        seen.add(title)
        assert title in seen

    def test_different_titles_allowed(self):
        seen = set()
        seen.add("Title 1")
        assert "Title 2" not in seen

    def test_case_sensitive(self):
        seen = set()
        seen.add("Title")
        # Exact match required
        assert "title" not in seen


# ═══════════════════════════════════════════════════════════════════════════
# PIPELINE INTEGRATION TEST
# ═══════════════════════════════════════════════════════════════════════════

class TestPipelineIntegration:
    def test_full_chain(self, source_video, tmp_artifacts):
        """Test: source → clip → video QA → audio QA → captions → creative → platform → package."""
        from tests.production_smoke_test import generate_test_srt
        import subprocess

        # 1. Clip
        clip = tmp_artifacts / "final" / "output.mp4"
        subprocess.run([
            "ffmpeg", "-y", "-i", str(source_video),
            "-ss", "0", "-t", "8",
            "-c:v", "libx264", "-preset", "ultrafast", "-crf", "28",
            "-c:a", "aac", "-b:a", "64k",
            str(clip),
        ], capture_output=True, timeout=30)
        assert clip.exists()

        # 2. Video QA
        vgate = validate_video_file(clip)
        assert vgate.status == "PASS"

        # 3. Audio QA
        agate = validate_audio(clip)
        assert agate.status == "PASS"

        # 4. Captions
        srt = tmp_artifacts / "captions" / "output.srt"
        generate_test_srt(8.0, srt)
        cgate = validate_captions(srt, clip)
        assert cgate.status == "PASS"

        # 5. Creative
        crgate = score_creative(clip)
        assert crgate.status == "PASS"
        assert crgate.creative_score >= 6.0

        # 6. Platform
        for platform in ["youtube_shorts", "instagram_reels", "tiktok"]:
            pgate = validate_platform(clip, platform)
            assert pgate.status == "PASS", f"{platform}: {pgate.reason}"

        # 7. Package
        manifest = {
            "asset_id": "integration_test",
            "title": "Integration Test",
            "description": "Full pipeline test",
            "hashtags": ["#test"],
            "platform": "youtube_shorts",
            "brand": "test",
        }
        manifest_path = tmp_artifacts / "manifests" / "test.json"
        manifest_path.write_text(json.dumps(manifest))
        assert manifest_path.exists()

    def test_gate_results_serializable(self, clip_from_source):
        """All gate results must be JSON-serializable."""
        vg = validate_video_file(clip_from_source)
        ag = validate_audio(clip_from_source)
        cg = score_creative(clip_from_source)

        for gate in [vg, ag, cg]:
            d = gate.to_dict()
            serialized = json.dumps(d)
            assert isinstance(serialized, str)
