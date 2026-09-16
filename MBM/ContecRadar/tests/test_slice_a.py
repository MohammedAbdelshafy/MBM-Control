"""Tests for Commercial Radar Slice A offline scope (#62)."""

import unittest

from MBM.ContecRadar.slice_a import (
    SLICE_A_EXCLUSIONS,
    ExcludedOperationError,
    autonomous_approve,
    execute_campaign,
    generate_demo,
    mutate_external_db,
    run_slice_a,
    send_outreach,
)


def fixture_signals():
    return [
        {
            "signal_id": "sig-a1",
            "title": "AI estimating workflow for contractors",
            "body": "Contractors need faster estimating with verified takeoff workflow",
            "source": "offline_fixture",
        },
        {
            "signal_id": "sig-a2",
            "title": "AI estimating workflow for contractors",
            "body": "Second independent signal about contractor estimating pain",
            "source": "offline_fixture",
        },
    ]


class SliceATests(unittest.TestCase):
    @staticmethod
    def _stable(opportunities):
        # Timestamps (first_seen/last_seen) are wall-clock evidence markers;
        # commercial determinism is scores/decisions/titles.
        stable = []
        for opp in opportunities:
            stable.append(
                {
                    "cluster_name": opp.get("cluster_name"),
                    "title": opp.get("title"),
                    "score": opp.get("score"),
                    "decision": opp.get("decision"),
                    "signal_count": opp.get("signal_count"),
                }
            )
        return stable

    def test_offline_run_deterministic(self):
        first = run_slice_a(fixture_signals())
        second = run_slice_a(fixture_signals())
        self.assertEqual(self._stable(first.opportunities), self._stable(second.opportunities))
        self.assertGreaterEqual(len(first.opportunities), 1)
        self.assertEqual(first.scope, "offline_signal_to_ranked_opportunity")
        self.assertEqual(first.diagnostics["side_effects"], "none")
        self.assertEqual(first.diagnostics["writes"], "none")

    def test_exclusions_preserved(self):
        result = run_slice_a(fixture_signals())
        for exclusion in (
            "no_outbound_sending",
            "no_campaign_execution",
            "no_external_db_runtime_mutation",
            "no_autonomous_approval_queue",
            "no_demo_generation",
        ):
            self.assertIn(exclusion, result.exclusions_preserved)
        self.assertEqual(sorted(result.exclusions_preserved), sorted(SLICE_A_EXCLUSIONS))

    def test_excluded_operations_fail_closed(self):
        with self.assertRaises(ExcludedOperationError):
            send_outreach({"to": "x"})
        with self.assertRaises(ExcludedOperationError):
            execute_campaign({"id": "c"})
        with self.assertRaises(ExcludedOperationError):
            mutate_external_db({"table": "t"})
        with self.assertRaises(ExcludedOperationError):
            autonomous_approve({"id": "q"})
        with self.assertRaises(ExcludedOperationError):
            generate_demo({"brief": "b"})

    def test_malformed_signal_fail_closed(self):
        with self.assertRaises(ValueError):
            run_slice_a([{"title": "no id"}])
        with self.assertRaises(ValueError):
            run_slice_a(["not-a-dict"])

    def test_empty_input(self):
        result = run_slice_a([])
        self.assertEqual(result.opportunities, [])
        self.assertEqual(result.diagnostics["signal_count"], 0)


if __name__ == "__main__":
    unittest.main()
