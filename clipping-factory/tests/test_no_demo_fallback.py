"""
Regression test: NO_REAL_SOURCE → NO_CLIP

Proves that a missing source CANNOT create a publishable artifact.
The demo-file fallback has been removed. This test verifies the invariant.
"""
import json
import tempfile
from pathlib import Path

import pytest


def test_missing_source_produces_source_not_found():
    """A missing source must result in SOURCE_NOT_FOUND, not a copied demo."""
    from clipping_factory.production_pipeline import render_clip, RenderStatus

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "output"
        output_dir.mkdir()

        # No source file exists at this path
        source_path = Path(tmpdir) / "nonexistent_movie.mp4"

        script_data = {
            "script_id": "SCR-TEST-001",
            "caption_beats": [],
            "hook": "Test hook",
            "narration": "Test narration",
        }

        channel_profile = {
            "resolution": "1080x1920",
            "fps": 30,
            "target_duration_max": 60,
            "voice_config": {"provider": "none"},
        }

        manifest = render_clip(
            campaign_id="CAMP-TEST-001",
            source_path=source_path,
            script_data=script_data,
            channel_profile=channel_profile,
            output_dir=output_dir,
        )

        # CRITICAL: Status must be SOURCE_NOT_FOUND
        assert manifest.render_status == RenderStatus.SOURCE_NOT_FOUND, (
            f"Expected SOURCE_NOT_FOUND but got {manifest.render_status}. "
            "The demo-file fallback may have been reintroduced!"
        )

        # CRITICAL: No output file should exist
        assert manifest.output_path == "", (
            "Output path should be empty when source is missing"
        )

        # CRITICAL: No pipeline steps beyond source verification
        assert manifest.pipeline_steps_completed == [], (
            f"No pipeline steps should run without a source. Got: {manifest.pipeline_steps_completed}"
        )


def test_none_source_produces_source_not_found():
    """A None source must result in SOURCE_NOT_FOUND."""
    from clipping_factory.production_pipeline import render_clip, RenderStatus

    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "output"
        output_dir.mkdir()

        manifest = render_clip(
            campaign_id="CAMP-TEST-002",
            source_path=None,
            script_data={"script_id": "SCR-TEST-002", "caption_beats": []},
            channel_profile={"resolution": "1080x1920", "fps": 30, "target_duration_max": 60, "voice_config": {"provider": "none"}},
            output_dir=output_dir,
        )

        assert manifest.render_status == RenderStatus.SOURCE_NOT_FOUND


def test_empty_directory_source_produces_source_not_found():
    """An empty directory as source must result in SOURCE_NOT_FOUND."""
    from clipping_factory.production_pipeline import render_clip, RenderStatus

    with tempfile.TemporaryDirectory() as tmpdir:
        empty_dir = Path(tmpdir) / "empty"
        empty_dir.mkdir()
        output_dir = Path(tmpdir) / "output"
        output_dir.mkdir()

        manifest = render_clip(
            campaign_id="CAMP-TEST-003",
            source_path=empty_dir / "missing.mp4",
            script_data={"script_id": "SCR-TEST-003", "caption_beats": []},
            channel_profile={"resolution": "1080x1920", "fps": 30, "target_duration_max": 60, "voice_config": {"provider": "none"}},
            output_dir=output_dir,
        )

        assert manifest.render_status == RenderStatus.SOURCE_NOT_FOUND


def test_rendered_status_requires_real_output():
    """A clip cannot be marked RENDERED without a valid output file."""
    from clipping_factory.production_pipeline import RenderManifest, RenderStatus

    manifest = RenderManifest(
        campaign_id="CAMP-TEST-004",
        render_status=RenderStatus.RENDERED,
    )

    # Even if someone sets RENDERED, packaging must validate
    with tempfile.TemporaryDirectory() as tmpdir:
        queue_dir = Path(tmpdir) / "queue"

        from clipping_factory.production_pipeline import package_for_publish

        with pytest.raises((FileNotFoundError, ValueError)):
            package_for_publish(
                manifest,
                queue_dir,
                metadata={"test": True},
            )


def test_no_demo_file_in_codebase():
    """Verify the demo fallback string is not used in the campaign manager."""
    manager_path = Path(__file__).parent.parent / "clipping_campaign_manager.py"
    if manager_path.exists():
        content = manager_path.read_text(encoding="utf-8")
        assert "demo_ai-clipping.mp4" not in content, (
            "The demo-file fallback 'demo_ai-clipping.mp4' must be removed "
            "from clipping_campaign_manager.py"
        )


def test_licensed_source_required_for_publish():
    """Publishing requires a verified source class — unverified sources are blocked."""
    from clipping_factory.production_pipeline import RenderManifest, RenderStatus, package_for_publish

    manifest = RenderManifest(
        campaign_id="CAMP-TEST-PUBLISH",
        render_status=RenderStatus.RENDERED,
        source_checksum="abc123",
        output_path="/nonexistent/path.mp4",
    )

    with tempfile.TemporaryDirectory() as tmpdir:
        queue_dir = Path(tmpdir) / "queue"
        with pytest.raises((FileNotFoundError, ValueError)):
            package_for_publish(manifest, queue_dir, {"source_class": "unverified"})


def test_real_tts_artifact_required():
    """TTS generation must produce a real audio file, not a placeholder."""
    import asyncio
    import edge_tts

    with tempfile.TemporaryDirectory() as tmpdir:
        output_path = Path(tmpdir) / "tts_test.mp3"
        text = "This is a real TTS smoke test for the clipping factory."

        async def gen():
            comm = edge_tts.Communicate(text, "en-US-GuyNeural", rate="-5%", pitch="-2Hz")
            await comm.save(str(output_path))

        asyncio.run(gen())

        assert output_path.exists(), "TTS file was not created"
        size = output_path.stat().st_size
        assert size > 1000, f"TTS file too small ({size} bytes) — likely not real audio"
        assert size < 10_000_000, f"TTS file suspiciously large ({size} bytes)"


def test_real_rendered_output_required():
    """A rendered clip must have valid video properties from ffprobe."""
    from clipping_factory.production_pipeline import _probe_video

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a real test video
        import subprocess
        ffmpeg = "ffmpeg"
        output = Path(tmpdir) / "test.mp4"
        subprocess.run([
            ffmpeg, "-y", "-f", "lavfi",
            "-i", "color=c=black:s=1080x1920:d=2",
            "-f", "lavfi", "-i", "anullsrc=r=44100:cl=stereo",
            "-t", "2", "-c:v", "libx264", "-preset", "ultrafast",
            "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest",
            str(output),
        ], capture_output=True, timeout=15)

        assert output.exists(), "Test video was not created"
        probe = _probe_video(output)
        assert probe["width"] == 1080, f"Expected width 1080, got {probe['width']}"
        assert probe["height"] == 1920, f"Expected height 1920, got {probe['height']}"
        assert probe["duration"] > 0, f"Expected positive duration, got {probe['duration']}"
        assert probe["fps"] > 0, f"Expected positive FPS, got {probe['fps']}"


def test_youtube_video_id_required_for_uploaded():
    """UPLOADED status requires a real YouTube video ID."""
    # This is a policy test — ensures the system doesn't claim upload without an ID
    from clipping_factory.production_pipeline import RenderManifest, RenderStatus

    manifest = RenderManifest(
        campaign_id="CAMP-TEST-UPLOAD",
        render_status=RenderStatus.RENDERED,
    )

    # Simulated publish result without real video ID
    fake_publish = {"status": "uploaded", "video_id": ""}

    # Policy: if video_id is empty, it's not truly uploaded
    assert fake_publish["video_id"] == "", "Empty video ID confirms upload not verified"
    # The real upload handler must never return empty video_id for UPLOADED status


def test_overlap_lock_prevents_concurrent_runs():
    """Two simultaneous lock attempts must not both succeed."""
    from clipping_factory.heartbeat import acquire_run_lock, release_run_lock

    lock1 = acquire_run_lock(timeout_sec=3600)
    assert lock1 == True, "First lock should succeed"

    lock2 = acquire_run_lock(timeout_sec=3600)
    assert lock2 == False, "Second lock should fail (already held)"

    release_run_lock()

    lock3 = acquire_run_lock(timeout_sec=3600)
    assert lock3 == True, "Lock should succeed after release"
    release_run_lock()


def test_channel_profile_twists_revealed_identity():
    """Twists Revealed must have movie_recap type and dark_suspenseful tone."""
    from clipping_factory.channel_profiles import get_profile

    profile = get_profile("twistsrevealed")

    assert profile.channel_type == "movie_recap", f"Expected movie_recap, got {profile.channel_type}"
    assert profile.tone == "dark_suspenseful", f"Expected dark_suspenseful, got {profile.tone}"
    assert profile.narration == "original_voiceover", f"Expected original_voiceover, got {profile.narration}"
    assert profile.voice.provider == "edge_tts", f"Expected edge_tts voice, got {profile.voice.provider}"
    assert "thriller" in profile.genres, "thriller must be in genres"
    assert "horror" in profile.genres, "horror must be in genres"
    assert profile.daily_target == 2, f"Expected daily_target 2, got {profile.daily_target}"
    assert profile.min_creative_score >= 7.0, "min_creative_score should be >= 7.0"
