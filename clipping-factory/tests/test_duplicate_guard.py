"""Duplicate-guard regression tests.

Live defect (2026-08-24 16:09 run): TR-1920-A38FE1F94821 was re-produced
end-to-end despite ready_to_publish state since 23/08. Root cause:
_load_state() silently returned {} on any read/parse failure (OneDrive sync
race), disabling BOTH the discovery exclusion and the _produce_one guard.
The guard is now fail-closed on unreadable state."""
import json
import sys
import tempfile
import unittest
import unittest.mock
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from clipping_factory import full_cycle
from clipping_factory.movie_discovery import MovieCandidate
from clipping_factory.channel_profiles import get_profile


def _candidate(cid="TR-1920-A38FE1F94821"):
    return MovieCandidate(
        campaign_id=cid, title="The Cabinet of Dr. Caligari", year=1920,
        director="Robert Wiene", genres=["horror"], rating=8.0,
        synopsis="s", ending_description="e", key_characters=[],
        source_class="public_domain",
        source_uri="https://archive.org/download/x/x.mp4",
    )


class TestDuplicateGuard(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.status_file = Path(self.tmp.name) / "movie_status.json"
        self._orig = full_cycle.STATUS_FILE
        full_cycle.STATUS_FILE = self.status_file
        self.addCleanup(setattr, full_cycle, "STATUS_FILE", self._orig)

    def _write_status(self, doc):
        self.status_file.write_text(json.dumps(doc), encoding="utf-8")

    def test_terminal_state_skips_production(self):
        """THE regression: ready_to_publish campaign must not be re-produced."""
        self._write_status({"TR-1920-A38FE1F94821": {"status": "ready_to_publish"}})
        res = full_cycle._produce_one(_candidate(), get_profile("twistsrevealed"),
                                      "TESTRUN", publish=False)
        self.assertEqual(res["status"], "skipped_duplicate")

    def test_published_and_verified_also_skip(self):
        for terminal in ("published", "verified"):
            self._write_status({"X": {"status": terminal}})
            res = full_cycle._produce_one(
                _candidate("X"), get_profile("twistsrevealed"), "TESTRUN", False)
            self.assertEqual(res["status"], "skipped_duplicate")

    def test_corrupt_state_fails_closed(self):
        """Unreadable state must SKIP production, never silently duplicate."""
        self.status_file.write_text("{corrupt json!!!", encoding="utf-8")
        res = full_cycle._produce_one(_candidate(), get_profile("twistsrevealed"),
                                      "TESTRUN", publish=False)
        self.assertEqual(res["status"], "skipped_state_unreadable")

    def test_nonterminal_state_allows_production_attempt(self):
        """failed/blocked/absent state must NOT trigger the guard.

        acquire_source is mocked to return SOURCE_BLOCKED so the test proves
        only that execution PASSED the guard, without any network/render work."""
        from clipping_factory.source_acquisition import SourceResult
        for st in ("failed", "blocked", "researched"):
            self._write_status({"TR-1920-A38FE1F94821": {"status": st}})
            with unittest.mock.patch.object(
                    full_cycle, "acquire_source",
                    return_value=SourceResult(
                        campaign_id="TR-1920-A38FE1F94821", status="blocked",
                        source_class="public_domain", provenance="public_domain",
                        uri="x", error="SOURCE_BLOCKED: unit-test stub")):
                res = full_cycle._produce_one(_candidate(),
                                              get_profile("twistsrevealed"),
                                              "TESTRUN", publish=False)
            self.assertEqual(res["status"], "source_blocked")

    def test_terminal_campaign_ids_helper(self):
        state = {
            "a": {"status": "ready_to_publish"},
            "b": {"status": "published"},
            "c": {"status": "verified"},
            "d": {"status": "failed"},
            "e": "not-a-dict",
        }
        self.assertEqual(sorted(full_cycle._terminal_campaign_ids(state)),
                         ["a", "b", "c"])
        self.assertEqual(full_cycle._terminal_campaign_ids(None), [])

    def test_read_status_file_retries_then_none(self):
        self.status_file.write_text("{still corrupt", encoding="utf-8")
        with unittest.mock.patch.object(full_cycle.time, "sleep"):
            self.assertIsNone(full_cycle._read_status_file())
        self.status_file.unlink()
        self.assertEqual(full_cycle._read_status_file(), {})

    def test_artifact_reconciliation_blocks_state_regression(self):
        """THE 18:01 live defect: state lost ready_to_publish, artifact didn't.

        With NO state entry at all, an existing packaged artifact dir must
        still force skipped_duplicate."""
        full_cycle.invalidate_artifact_cache()
        self.addCleanup(full_cycle.invalidate_artifact_cache)
        artifacts = Path(self.tmp.name) / "artifacts"
        artifacts.mkdir()
        self.addCleanup(setattr, full_cycle, "ARTIFACTS_ROOT",
                        Path(self.tmp.name) / "orig_artifacts_absent")
        full_cycle.ARTIFACTS_ROOT = artifacts
        cid = "TR-1922-B02CE02259AB"
        d = artifacts / f"20260823_180547_{cid}"
        d.mkdir(parents=True)
        (d / "publish_package.json").write_text("{}", encoding="utf-8")

        # no state file at all -> state barrier silent
        res = full_cycle._produce_one(_candidate(cid), get_profile("twistsrevealed"),
                                      "TESTRUN", publish=False)
        self.assertEqual(res["status"], "skipped_duplicate")

    def test_artifact_cache_invalidated_on_production(self):
        """invalidate_artifact_cache clears the memoized map."""
        full_cycle.invalidate_artifact_cache()
        first = full_cycle._produced_artifact_campaigns()
        again = full_cycle._produced_artifact_campaigns()
        self.assertIs(first, again)
        full_cycle.invalidate_artifact_cache()
        self.assertIsNot(first, full_cycle._produced_artifact_campaigns())

    def test_dirs_without_package_are_not_terminal(self):
        """Campaign dirs missing publish_package.json (failed/rejected runs)
        must NOT count as produced."""
        full_cycle.invalidate_artifact_cache()
        self.addCleanup(full_cycle.invalidate_artifact_cache)
        artifacts = Path(self.tmp.name) / "artifacts2"
        artifacts.mkdir(parents=True)
        orig_root = full_cycle.ARTIFACTS_ROOT
        full_cycle.ARTIFACTS_ROOT = artifacts
        self.addCleanup(setattr, full_cycle, "ARTIFACTS_ROOT", orig_root)
        d = artifacts / "20260824_000000_TR-9999-DEADBEEF00"
        d.mkdir(parents=True)
        (d / "campaign.json").write_text("{}", encoding="utf-8")  # no package
        self.assertFalse(
            full_cycle._produced_artifact_campaigns().get("TR-9999-DEADBEEF00", False))


if __name__ == "__main__":
    unittest.main()
