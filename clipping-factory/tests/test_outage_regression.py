"""Regression tests for the 2026-08-24 production outage.

Failure chain that broke every scheduled cycle since 23/08 evening:
  1. ffprobe returned 0s on a cached source (OneDrive hydration contention)
  2. acquire_source kept status="cached" while returning local_path=""
  3. full_cycle passed the gate -> Path("") == "." -> PermissionError '.'
All three layers are now guarded; these tests pin the contract.
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clipping_factory.source_acquisition import SourceResult, _ffprobe_duration, acquire_source
from clipping_factory import full_cycle
from clipping_factory import source_acquisition as sa


class TestProbeRetry(unittest.TestCase):
    def test_transient_probe_failure_recovers_via_retry(self):
        """A transient 0.0 ffprobe result is retried and recovers."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)

            src_dir = tmp_path / "retry_movie_1962"
            src_dir.mkdir(parents=True)

            source = src_dir / "source.mp4"
            source.write_bytes(b"\x00" * (11 * 1024 * 1024))

            with mock.patch.object(sa, "SOURCES_DIR", tmp_path), \
                 mock.patch.object(
                     sa,
                     "_ffprobe_duration",
                     side_effect=[0.0, 4909.16],
                 ) as mock_probe:

                result = sa.acquire_source(
                    "TEST-RETRY",
                    "Retry Movie",
                    1962,
                    "public_domain",
                    "https://example.invalid/m.mp4",
                )

        self.assertEqual(result.status, "cached")
        self.assertAlmostEqual(result.duration_sec, 4909.16, places=2)
        self.assertTrue(result.local_path)
        self.assertEqual(mock_probe.call_count, 2)

    def test_ffprobe_duration_returns_zero_on_garbage(self):
        p = Path(__file__)  # not a video: ffprobe fails or returns nothing
        self.assertEqual(_ffprobe_duration(p, timeout_sec=10), 0.0)

    def test_ffprobe_duration_returns_zero_on_garbage(self):
        p = Path(__file__)  # not a video: ffprobe fails or returns nothing
        self.assertEqual(_ffprobe_duration(p, timeout_sec=10), 0.0)


class TestAcquireSourceContract(unittest.TestCase):
    def setUp(self):
        # isolated sources dir with an UNPROBEABLE cached "feature" file
        import tempfile
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        src_dir = Path(self.tmp.name) / "some_movie_1962"
        src_dir.mkdir(parents=True)
        self.movie_file = src_dir / "source.mp4"
        big = b"\x00" * (11 * 1024 * 1024)  # > MIN_SOURCE_BYTES, not a real video
        self.movie_file.write_bytes(big)

    def _acquire(self):
        return acquire_source(
            campaign_id="TEST-REG",
            title="Some Movie", year=1962,
            source_class="public_domain",
            source_uri="https://example.invalid/movie.mp4",
            allowed_provenance=["public_domain"],
        )

    def test_unprobeable_cached_source_is_blocked_not_cached(self):
        """THE regression: garbage cached file must yield status='blocked'."""
        with mock.patch.object(sa, "SOURCES_DIR",
                               Path(self.tmp.name)):
            result = self._acquire()
        self.assertEqual(result.status, "blocked")
        self.assertTrue(result.error.startswith("SOURCE_BLOCKED"))
        self.assertEqual(result.local_path, "")

    def test_blocked_result_fails_full_cycle_gate(self):
        with mock.patch.object(sa, "SOURCES_DIR",
                               Path(self.tmp.name)):
            result = self._acquire()
        self.assertFalse(result.status in ("acquired", "cached"))


class TestFullCycleGate(unittest.TestCase):
    def test_source_usable_rejects_empty_local_path(self):
        """Path('') == '.' must never reach copyfile."""
        src = SourceResult(campaign_id="T", status="cached", source_class="public_domain",
                           provenance="public_domain", uri="x", local_path="")
        self.assertFalse(full_cycle._source_usable(src))

    def test_source_usable_rejects_missing_file(self):
        src = SourceResult(campaign_id="T", status="cached", source_class="public_domain",
                           provenance="public_domain", uri="x",
                           local_path=r"Z:\definitely\not\here.mp4")
        self.assertFalse(full_cycle._source_usable(src))

    def test_source_usable_accepts_real_file(self):
        src = SourceResult(campaign_id="T", status="cached", source_class="public_domain",
                           provenance="public_domain", uri="x", local_path=str(__file__))
        self.assertTrue(full_cycle._source_usable(src))


class TestAcquireSourceResilience(unittest.TestCase):
    """Scenarios 5/8/10/11/12 of the acquisition reliability matrix."""

    def _isolated_sources(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        return Path(tmp.name)

    def _write_source(self, sources_dir, slug, size_mb=11):
        d = Path(sources_dir) / slug
        d.mkdir(parents=True, exist_ok=True)
        f = d / "source.mp4"
        f.write_bytes(b"\x00" * (size_mb * 1024 * 1024))
        return f

    def _acquire(self, sources_dir, title="Retry Movie", year=1962,
                 uri="https://example.invalid/m.mp4"):
        with mock.patch.object(sa, "SOURCES_DIR", sources_dir), \
             mock.patch.object(sa, "_ffprobe_duration", return_value=4909.16):
            return sa.acquire_source("TEST-RES", title, year,
                                     "public_domain", uri)

    def test_download_failure_returns_blocked(self):
        """Missing file + failing download -> blocked, never fabricated."""
        sources = self._isolated_sources()
        with mock.patch.object(sa, "SOURCES_DIR", sources), \
             mock.patch.object(sa, "_download", return_value=False):
            result = sa.acquire_source("TEST-DLFAIL", "Ghost Movie", 1955,
                                       "public_domain", "https://example.invalid/g.mp4")
        self.assertEqual(result.status, "blocked")
        self.assertIn("download failed", result.error)
        self.assertEqual(result.local_path, "")

    def test_duplicate_acquire_reuses_cached_no_second_download(self):
        """Idempotency: second acquire reuses the cached file, never redownloads."""
        sources = self._isolated_sources()
        self._write_source(sources, "retry_movie_1962")
        first = self._acquire(sources)
        with mock.patch.object(sa, "_download",
                               side_effect=AssertionError("must not redownload")):
            second = self._acquire(sources)
        self.assertEqual(first.status, "cached")
        self.assertEqual(second.status, "cached")
        self.assertEqual(Path(first.local_path), Path(second.local_path))

    def test_corrupt_source_blocks_then_repairs_after_replace(self):
        """Corrupt cache -> blocked (no silent reuse); replacing the file heals."""
        sources = self._isolated_sources()
        slug = "corrupt_movie_1964"
        corrupt = self._write_source(sources, slug)

        with mock.patch.object(sa, "SOURCES_DIR", sources), \
             mock.patch.object(sa, "_ffprobe_duration", return_value=0.0):
            blocked = sa.acquire_source("TEST-CORRUPT", "Corrupt Movie", 1964,
                                        "public_domain", "https://example.invalid/c.mp4")
        self.assertEqual(blocked.status, "blocked")

        # repair: operator/pipeline replaces the file with a valid one
        corrupt.write_bytes(b"\x00" * (12 * 1024 * 1024))
        with mock.patch.object(sa, "SOURCES_DIR", sources), \
             mock.patch.object(sa, "_ffprobe_duration", return_value=4833.0), \
             mock.patch.object(sa, "_download",
                               side_effect=AssertionError("repair must not redownload")):
            repaired = sa.acquire_source("TEST-CORRUPT", "Corrupt Movie", 1964,
                                         "public_domain", "https://example.invalid/c.mp4")
        self.assertEqual(repaired.status, "cached")
        self.assertAlmostEqual(repaired.duration_sec, 4833.0, places=2)


if __name__ == "__main__":
    unittest.main()


