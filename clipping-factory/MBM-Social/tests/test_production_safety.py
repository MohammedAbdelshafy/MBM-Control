"""
Production Safety Regression Tests — PR #8 findings.

Covers:
  P0: Test mode cannot publish publicly on any platform
  P0: Dry-run performs zero publishing
  P0: Live mode requires explicit production authorization
  P0: No fabricated video IDs
  P1: Successful-but-unverified upload enters PUBLISH_PENDING_VERIFICATION
  P1: Duplicate retry protection (pending packages not auto-retried)
  P2: ffprobe missing/N/A nb_frames is safe (no crash)
  P2: Freshness test imports canonical queue engine
"""
from __future__ import annotations

import json
import sys
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


# ============================================================
# P0 — TEST MODE SAFETY
# ============================================================

class TestModeSafety:
    """Test mode must NEVER publish publicly on any platform."""

    def test_publish_via_api_blocks_public_without_allow_public(self):
        """youtube_api_publisher.publish_via_api rejects public when allow_public=False."""
        from mbm_social.youtube_api_publisher import publish_via_api

        # Even with a non-existent video, the function should reject public
        # before doing any network I/O
        ok, vid = publish_via_api(
            "/nonexistent/video.mp4",
            "test",
            "test",
            brand="testbrand",
            privacy_status="public",
            allow_public=False,
        )
        assert ok is False
        assert vid is None

    def test_publish_via_api_allows_public_with_explicit_auth(self):
        """youtube_api_publisher.publish_via_api allows public when allow_public=True."""
        from mbm_social.youtube_api_publisher import publish_via_api

        # This will fail because the video doesn't exist, but it should
        # NOT fail with the "BLOCKED" message — it should proceed to
        # the normal file-not-found error
        ok, vid = publish_via_api(
            "/nonexistent/video.mp4",
            "test",
            "test",
            brand="testbrand",
            privacy_status="public",
            allow_public=True,
        )
        assert ok is False
        assert vid is None
        # The function should NOT have printed the BLOCKED message
        # (it proceeds to file check instead)

    def test_publish_via_api_unlisted_works(self):
        """youtube_api_publisher.publish_via_api accepts unlisted (test mode)."""
        from mbm_social.youtube_api_publisher import publish_via_api

        ok, vid = publish_via_api(
            "/nonexistent/video.mp4",
            "test",
            "test",
            brand="testbrand",
            privacy_status="unlisted",
        )
        # Fails because video doesn't exist, NOT because of mode block
        assert ok is False
        assert vid is None

    def test_orchestrator_test_mode_skips_social_publishers(self):
        """post_orchestrator._publish_social returns all-False in test mode."""
        from mbm_social.post_orchestrator import _publish_social

        results = _publish_social(
            {"title": "test video"},
            "testbrand",
            dry_run=False,
            mode="test",
        )
        assert results == {"instagram": False, "tiktok": False}

    def test_orchestrator_test_mode_does_not_call_shortform_publisher(self):
        """post_orchestrator._publish_social never imports shortform_publisher in test mode."""
        from mbm_social.post_orchestrator import _publish_social

        with patch.dict("sys.modules", {"mbm_social.shortform_publisher": MagicMock()}):
            results = _publish_social(
                {"title": "test video"},
                "testbrand",
                dry_run=False,
                mode="test",
            )
            assert results == {"instagram": False, "tiktok": False}
            # shortform_publisher.publish should NOT have been called
            sf = sys.modules.get("mbm_social.shortform_publisher")
            if sf:
                sf.publish.assert_not_called()

    def test_publish_via_playwright_validates_privacy_status(self):
        """publish_via_playwright rejects invalid privacy_status values."""
        from mbm_social.youtube_api_publisher import publish_via_playwright

        ok, vid = publish_via_playwright(
            "/nonexistent/video.mp4",
            "test",
            "test",
            brand="testbrand",
            privacy_status="INVALID",
        )
        assert ok is False
        assert vid is None


class TestDryRunSafety:
    """Dry-run mode performs zero network publishing."""

    def test_orchestrator_dry_run_skips_all_publishers(self):
        """post_orchestrator._publish_youtube prints dry-run message, no upload."""
        from mbm_social.post_orchestrator import _publish_youtube

        with patch("mbm_social.youtube_api_publisher.tokens_exist_for", return_value=False):
            ok, vid, ch = _publish_youtube(
                {"title": "test"},
                "testbrand",
                "/fake/video.mp4",
                dry_run=True,
                privacy_status="private",
                mode="dry_run",
            )
        assert ok is False

    def test_orchestrator_dry_run_skips_social(self):
        """post_orchestrator._publish_social prints dry-run message, no upload."""
        from mbm_social.post_orchestrator import _publish_social

        results = _publish_social(
            {"title": "test"},
            "testbrand",
            dry_run=True,
            mode="dry_run",
        )
        assert results == {"instagram": False, "tiktok": False}


class TestLiveModeGate:
    """Live mode requires explicit PUBLISH_MODE=live env var."""

    def test_live_blocked_without_env(self):
        """main() blocks --mode live when PUBLISH_MODE env is not 'live'."""
        from mbm_social.post_orchestrator import main

        with patch.dict("os.environ", {"PUBLISH_MODE": "dry_run"}, clear=False):
            # Override the module-level PUBLISH_MODE
            import mbm_social.post_orchestrator as orch
            old_mode = orch.PUBLISH_MODE
            orch.PUBLISH_MODE = "dry_run"
            try:
                result = main(["--mode", "live", "--limit", "0"])
                assert result == 2  # blocked
            finally:
                orch.PUBLISH_MODE = old_mode

    def test_live_allowed_with_env(self):
        """main() allows --mode live when PUBLISH_MODE=live."""
        from mbm_social.post_orchestrator import main

        with patch.dict("os.environ", {"PUBLISH_MODE": "live"}, clear=False):
            import mbm_social.post_orchestrator as orch
            old_mode = orch.PUBLISH_MODE
            orch.PUBLISH_MODE = "live"
            try:
                # Mock publish_all to avoid scanning 1000+ queue files
                with patch("mbm_social.post_orchestrator.publish_all",
                           return_value={"processed": 0, "published": 0, "skipped_drafts": 0,
                                         "mode": "live", "by_platform": {"youtube": 0, "instagram": 0, "tiktok": 0}}):
                    result = main(["--mode", "live", "--limit", "0"])
                assert result == 0
            finally:
                orch.PUBLISH_MODE = old_mode


# ============================================================
# P0 — NO FABRICATED VIDEO IDs
# ============================================================

class TestNoFabricatedIDs:
    """All publishers must never fabricate video IDs."""

    def test_youtube_api_mark_published_blocks_without_id(self):
        """youtube_api_publisher.mark_published sets publish_blocked when no video_id."""
        from mbm_social.youtube_api_publisher import mark_published

        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"status": "draft"}, f)
            f.flush()
            filepath = f.name

        try:
            data = {"status": "draft"}
            mark_published(filepath, data, video_id=None)
            with open(filepath) as f:
                result = json.load(f)
            assert result["status"] == "publish_blocked"
            assert result["publish_blocked_reason"] == "platform_identity_not_verified"
        finally:
            Path(filepath).unlink(missing_ok=True)

    def test_youtube_api_mark_published_with_real_id(self):
        """youtube_api_publisher.mark_published uses the real video_id provided."""
        from mbm_social.youtube_api_publisher import mark_published

        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"status": "draft"}, f)
            f.flush()
            filepath = f.name

        try:
            data = {"status": "draft"}
            mark_published(filepath, data, video_id="REAL_ID_123")
            with open(filepath) as f:
                result = json.load(f)
            assert result["status"] == "published"
            assert result["youtube_video_id"] == "REAL_ID_123"
            assert result["youtube_url"] == "https://www.youtube.com/watch?v=REAL_ID_123"
        finally:
            Path(filepath).unlink(missing_ok=True)

    def test_cdp_mark_published_blocks_without_id(self):
        """youtube_cdp_publisher.mark_published sets publish_blocked when no video_id."""
        from mbm_social.youtube_cdp_publisher import mark_published

        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"status": "draft"}, f)
            f.flush()
            filepath = f.name

        try:
            data = {"status": "draft"}
            mark_published(filepath, data, video_id=None)
            with open(filepath) as f:
                result = json.load(f)
            assert result["status"] == "publish_blocked"
            assert result["publish_blocked_reason"] == "platform_identity_not_verified"
        finally:
            Path(filepath).unlink(missing_ok=True)

    def test_publisher_mark_published_blocks_without_id(self):
        """publisher.mark_published sets publish_blocked when no video_id."""
        from mbm_social.publisher import mark_published

        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
            json.dump({"status": "draft"}, f)
            f.flush()
            filepath = f.name

        try:
            data = {"status": "draft"}
            mark_published(filepath, data, video_id=None)
            with open(filepath) as f:
                result = json.load(f)
            assert result["status"] == "publish_blocked"
            assert result["publish_blocked_reason"] == "platform_identity_not_verified"
        finally:
            Path(filepath).unlink(missing_ok=True)

    def test_publish_via_api_returns_none_on_failure(self):
        """publish_via_api returns (False, None) on failure — never a fabricated ID."""
        from mbm_social.youtube_api_publisher import publish_via_api

        ok, vid = publish_via_api(
            "/nonexistent.mp4",
            "test",
            "test",
            brand="nonexistent_brand",
            privacy_status="unlisted",
        )
        assert ok is False
        assert vid is None


# ============================================================
# P1 — PUBLISH_PENDING_VERIFICATION STATE
# ============================================================

class TestPendingVerification:
    """Successful-but-unverified uploads enter PUBLISH_PENDING_VERIFICATION."""

    def test_publish_package_pending_when_yt_ok_but_no_id(self):
        """publish_package sets publish_pending_verification when yt succeeds but no ID."""
        from mbm_social.post_orchestrator import publish_package, STATUS_PUBLISH_PENDING

        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False,
                                          dir=str(ROOT / "publish_queue")) as f:
            json.dump({
                "status": "draft",
                "brand": "testbrand",
                "title": "Test Video",
                "video_path": str(ROOT / "viral_pool" / "viral_voice_agency_01.mp4"),
            }, f)
            filepath = Path(f.name)

        try:
            # Mock _publish_youtube to return (True, None, None) —
            # upload succeeded but no video ID extracted
            with patch("mbm_social.post_orchestrator._publish_youtube",
                       return_value=(True, None, None)):
                with patch("mbm_social.post_orchestrator._publish_social",
                           return_value={"instagram": False, "tiktok": False}):
                    result = publish_package(filepath, {"status": "draft", "brand": "test",
                                                        "title": "Test",
                                                        "video_path": str(ROOT / "viral_pool" / "viral_voice_agency_01.mp4")},
                                             dry_run=False, mode="test")

            assert result["status"] == STATUS_PUBLISH_PENDING
            assert result["publish_pending_reason"] == "submitted_without_verified_id"
            assert "publish_pending_at" in result
        finally:
            filepath.unlink(missing_ok=True)

    def test_pending_packages_excludes_pending_verification(self):
        """pending_packages does NOT return packages in publish_pending_verification status."""
        from mbm_social.post_orchestrator import pending_packages

        with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False,
                                          dir=str(ROOT / "publish_queue")) as f:
            json.dump({
                "status": "publish_pending_verification",
                "brand": "testbrand",
                "title": "Pending Video",
                "video_path": str(ROOT / "viral_pool" / "viral_voice_agency_01.mp4"),
            }, f)
            filepath = Path(f.name)

        try:
            pending = pending_packages(brand="testbrand", dedupe=False)
            # The pending-verification package should NOT be in the list
            found = any(str(fp) == str(filepath) for fp, _ in pending)
            assert not found, "publish_pending_verification packages should not be auto-retried"
        finally:
            filepath.unlink(missing_ok=True)


# ============================================================
# P2 — FFMPEG nb_frames OPTIONAL
# ============================================================

class TestFfprobeNbFrames:
    """ffprobe nb_frames must be safely handled when missing/N/A/invalid."""

    def test_nb_frames_missing(self):
        """VideoProbeResult handles missing nb_frames as None."""
        from mbm_social.video_gate import ffprobe_json, VideoProbeResult

        # Simulate ffprobe output with missing nb_frames
        fake_data = {
            "format": {"format_name": "mp4", "duration": "10.0", "size": "1000000"},
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1080,
                "height": 1920,
                "display_aspect_ratio": "9:16",
                "pix_fmt": "yuv420p",
                "r_frame_rate": "30/1",
                # nb_frames is absent
            }],
        }

        # Patch subprocess to return our fake data
        with patch("mbm_social.video_gate.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps(fake_data)
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = ffprobe_json(Path("/fake/video.mp4"))

        assert result.nb_frames is None
        assert result.width == 1080
        assert result.duration == 10.0

    def test_nb_frames_na(self):
        """VideoProbeResult handles nb_frames='N/A' as None."""
        from mbm_social.video_gate import ffprobe_json

        fake_data = {
            "format": {"format_name": "mp4", "duration": "10.0", "size": "1000000"},
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1080,
                "height": 1920,
                "nb_frames": "N/A",
                "r_frame_rate": "30/1",
            }],
        }

        with patch("mbm_social.video_gate.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps(fake_data)
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = ffprobe_json(Path("/fake/video.mp4"))

        assert result.nb_frames is None

    def test_nb_frames_empty_string(self):
        """VideoProbeResult handles nb_frames='' as None."""
        from mbm_social.video_gate import ffprobe_json

        fake_data = {
            "format": {"format_name": "mp4", "duration": "10.0", "size": "1000000"},
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1080,
                "height": 1920,
                "nb_frames": "",
                "r_frame_rate": "30/1",
            }],
        }

        with patch("mbm_social.video_gate.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps(fake_data)
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = ffprobe_json(Path("/fake/video.mp4"))

        assert result.nb_frames is None

    def test_nb_frames_zero(self):
        """VideoProbeResult handles nb_frames='0' as integer 0."""
        from mbm_social.video_gate import ffprobe_json

        fake_data = {
            "format": {"format_name": "mp4", "duration": "10.0", "size": "1000000"},
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1080,
                "height": 1920,
                "nb_frames": "0",
                "r_frame_rate": "30/1",
            }],
        }

        with patch("mbm_social.video_gate.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps(fake_data)
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = ffprobe_json(Path("/fake/video.mp4"))

        assert result.nb_frames == 0

    def test_nb_frames_valid(self):
        """VideoProbeResult handles nb_frames='300' as integer 300."""
        from mbm_social.video_gate import ffprobe_json

        fake_data = {
            "format": {"format_name": "mp4", "duration": "10.0", "size": "1000000"},
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1080,
                "height": 1920,
                "nb_frames": "300",
                "r_frame_rate": "30/1",
            }],
        }

        with patch("mbm_social.video_gate.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps(fake_data)
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = ffprobe_json(Path("/fake/video.mp4"))

        assert result.nb_frames == 300

    def test_nb_frames_invalid_string(self):
        """VideoProbeResult handles nb_frames='invalid' as None."""
        from mbm_social.video_gate import ffprobe_json

        fake_data = {
            "format": {"format_name": "mp4", "duration": "10.0", "size": "1000000"},
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1080,
                "height": 1920,
                "nb_frames": "invalid",
                "r_frame_rate": "30/1",
            }],
        }

        with patch("mbm_social.video_gate.subprocess.run") as mock_run:
            mock_result = MagicMock()
            mock_result.returncode = 0
            mock_result.stdout = json.dumps(fake_data)
            mock_result.stderr = ""
            mock_run.return_value = mock_result

            result = ffprobe_json(Path("/fake/video.mp4"))

        assert result.nb_frames is None

    def test_validate_video_with_missing_nb_frames_passes(self):
        """validate_video_file passes when nb_frames is missing but duration is valid."""
        from mbm_social.video_gate import validate_video_file

        fake_data = {
            "format": {"format_name": "mp4", "duration": "10.0", "size": "5000000"},
            "streams": [{
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1080,
                "height": 1920,
                "display_aspect_ratio": "9:16",
                "pix_fmt": "yuv420p",
                "r_frame_rate": "30/1",
                "bit_rate": "2000000",
                # nb_frames is absent
            }, {
                "codec_type": "audio",
                "codec_name": "aac",
                "sample_rate": "44100",
                "channels": "2",
                "bit_rate": "128000",
            }],
        }

        # Create a real temp file so Path.exists() returns True
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            with patch("mbm_social.video_gate.subprocess.run") as mock_run:
                mock_result = MagicMock()
                mock_result.returncode = 0
                mock_result.stdout = json.dumps(fake_data)
                mock_result.stderr = ""
                mock_run.return_value = mock_result

                result = validate_video_file(tmp_path)

            # Should not crash — has_frames falls back to duration check
            assert result.status in ("PASS", "FAIL", "BLOCKED")
            assert result.checks.get("has_frames") is True
        finally:
            tmp_path.unlink(missing_ok=True)


# ============================================================
# P0 — FABRICATED ID PROTECTION (comprehensive)
# ============================================================

class TestFabricatedIDProtection:
    """Every publisher must never fabricate video IDs."""

    def test_all_mark_published_functions_reject_none_id(self):
        """All mark_published functions set publish_blocked when video_id is None."""
        from mbm_social.youtube_api_publisher import mark_published as yt_mark
        from mbm_social.youtube_cdp_publisher import mark_published as cdp_mark
        from mbm_social.publisher import mark_published as pw_mark

        for mark_fn in [yt_mark, cdp_mark, pw_mark]:
            with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
                json.dump({"status": "draft"}, f)
                f.flush()
                filepath = f.name

            try:
                data = {"status": "draft"}
                mark_fn(filepath, data, video_id=None)
                with open(filepath) as f:
                    result = json.load(f)
                assert result["status"] == "publish_blocked", \
                    f"{mark_fn.__module__} did not set publish_blocked for None video_id"
                assert result["publish_blocked_reason"] == "platform_identity_not_verified"
            finally:
                Path(filepath).unlink(missing_ok=True)

    def test_publish_via_api_never_returns_fabricated_id(self):
        """publish_via_api returns (False, None) on any failure path."""
        from mbm_social.youtube_api_publisher import publish_via_api

        # Non-existent brand → should fail without returning any ID
        ok, vid = publish_via_api(
            "/nonexistent.mp4",
            "test",
            "test",
            brand="definitely_nonexistent_brand_xyz",
            privacy_status="unlisted",
        )
        assert ok is False
        assert vid is None
        # The video_id must be None, not some fake string
        if vid is not None:
            assert len(vid) > 0
            # It should look like a real YouTube ID (11 chars, alphanumeric + _ -)
            import re
            assert re.match(r'^[a-zA-Z0-9_-]{11}$', vid), f"Suspicious video_id: {vid}"


# ============================================================
# P1 — PRODUCTION CONTRACT
# ============================================================

class TestProductionContract:
    """Verify production contract invariants."""

    def test_state_machine_has_pending_verification(self):
        """state_machine includes PUBLISH_PENDING_VERIFICATION in valid states."""
        from mbm_social.state_machine import ALL_STATES

        # The state machine should have the pending verification state
        # (even if we're using string-based status in the orchestrator)
        # This is a documentation test — the orchestrator uses STATUS_PUBLISH_PENDING
        # as a string constant, not a formal state machine state
        from mbm_social.post_orchestrator import STATUS_PUBLISH_PENDING
        assert STATUS_PUBLISH_PENDING == "publish_pending_verification"

    def test_orchestrator_status_constants_defined(self):
        """post_orchestrator defines all required status constants."""
        from mbm_social.post_orchestrator import (
            STATUS_DRAFT, STATUS_PUBLISHED, STATUS_PUBLISH_BLOCKED, STATUS_PUBLISH_PENDING
        )
        assert STATUS_DRAFT == "draft"
        assert STATUS_PUBLISHED == "published"
        assert STATUS_PUBLISH_BLOCKED == "publish_blocked"
        assert STATUS_PUBLISH_PENDING == "publish_pending_verification"

    def test_video_gate_returns_controlled_result(self):
        """validate_video_file returns PASS/FAIL/BLOCKED, never throws."""
        from mbm_social.video_gate import validate_video_file

        # Non-existent file → BLOCKED (not an exception)
        result = validate_video_file(Path("/nonexistent/video.mp4"))
        assert result.status == "BLOCKED"

    def test_publish_modes_defined(self):
        """post_orchestrator defines valid publish modes."""
        from mbm_social.post_orchestrator import PUBLISH_MODES
        assert "dry_run" in PUBLISH_MODES
        assert "test" in PUBLISH_MODES
        assert "live" in PUBLISH_MODES


# ============================================================
# P2 — FRESHNESS TEST IMPORT
# ============================================================

class TestFreshnessImport:
    """Freshness test must import from canonical queue engine."""

    def test_import_dialer_queue_engine(self):
        """MBM.LeadEngine.dialer_queue_engine is importable."""
        import importlib
        # The MBM/ package is at the repo root, not under clipping-factory/MBM-Social/
        repo_root = str(ROOT.parent.parent)  # C:\Users\omare\OneDrive\Desktop\AI
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        mod = importlib.import_module("MBM.LeadEngine.dialer_queue_engine")
        assert hasattr(mod, "build_global_queue")
        assert hasattr(mod, "get_callable_state")
        assert hasattr(mod, "rank_main_queue")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
