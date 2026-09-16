"""Deterministic tests for Creator Acquisition Gate (#65)."""

import unittest
from datetime import datetime, timedelta, timezone

from MBM.DemandFactory.creator_gate import (
    CREATOR_MIN_AUDIENCE,
    EVIDENCE_MAX_AGE_DAYS,
    CreatorEvidence,
    assert_audience_isolation,
    evaluate_creator_evidence,
    qualify_creator_with_evidence,
)

NOW = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)


def valid_evidence(**overrides):
    base = {
        "platform": "youtube",
        "profile": "https://youtube.com/@example",
        "audience_type": "subscribers",
        "audience_count": 25000,
        "evidence_url": "https://youtube.com/@example/about",
        "evidence_source": "channel about page screenshot",
        "timestamp": (NOW - timedelta(days=7)).isoformat(),
    }
    base.update(overrides)
    return base


class CreatorGateTests(unittest.TestCase):
    def test_threshold_constant(self):
        self.assertEqual(CREATOR_MIN_AUDIENCE, 20000)

    def test_exact_threshold_qualifies(self):
        result = evaluate_creator_evidence(valid_evidence(audience_count=20000), now=NOW)
        self.assertEqual(result.status, "qualified")
        self.assertEqual(result.reasons, [])

    def test_one_below_threshold_rejected(self):
        result = evaluate_creator_evidence(valid_evidence(audience_count=19999), now=NOW)
        self.assertEqual(result.status, "rejected")
        self.assertIn("BELOW_THRESHOLD", result.reasons)

    def test_above_threshold_qualifies(self):
        result = evaluate_creator_evidence(valid_evidence(audience_count=20001), now=NOW)
        self.assertEqual(result.status, "qualified")

    def test_missing_fields_rejected(self):
        result = evaluate_creator_evidence({}, now=NOW)
        for code in (
            "MISSING_PLATFORM",
            "MISSING_PROFILE",
            "MISSING_AUDIENCE_TYPE",
            "MISSING_AUDIENCE_COUNT",
            "MISSING_EVIDENCE_URL",
            "MISSING_EVIDENCE_SOURCE",
            "MISSING_TIMESTAMP",
        ):
            self.assertIn(code, result.reasons)
        self.assertEqual(result.status, "rejected")

    def test_malformed_count_rejected(self):
        for bad in ("twenty thousand", "20.5k", 20.5, None, True, "20,000.0", "-5"):
            with self.subTest(bad=bad):
                payload = valid_evidence()
                payload["audience_count"] = bad
                if bad is None:
                    result = evaluate_creator_evidence(payload, now=NOW)
                    self.assertIn("MISSING_AUDIENCE_COUNT", result.reasons)
                else:
                    result = evaluate_creator_evidence(payload, now=NOW)
                    self.assertIn("MALFORMED_AUDIENCE_COUNT", result.reasons)
                    self.assertEqual(result.status, "rejected")

    def test_digit_string_with_separators_accepted(self):
        result = evaluate_creator_evidence(valid_evidence(audience_count="20,000"), now=NOW)
        self.assertEqual(result.status, "qualified")

    def test_malformed_url_rejected(self):
        for bad in ("not-a-url", "ftp://example.com/x", "", "   "):
            with self.subTest(bad=bad):
                result = evaluate_creator_evidence(valid_evidence(evidence_url=bad), now=NOW)
                self.assertEqual(result.status, "rejected")
                self.assertTrue(
                    "MISSING_EVIDENCE_URL" in result.reasons
                    or "MALFORMED_EVIDENCE_URL" in result.reasons
                )

    def test_malformed_timestamp_rejected(self):
        result = evaluate_creator_evidence(valid_evidence(timestamp="yesterday-ish"), now=NOW)
        self.assertIn("MALFORMED_TIMESTAMP", result.reasons)

    def test_future_evidence_rejected(self):
        future = (NOW + timedelta(days=1)).isoformat()
        result = evaluate_creator_evidence(valid_evidence(timestamp=future), now=NOW)
        self.assertIn("FUTURE_EVIDENCE", result.reasons)
        self.assertEqual(result.status, "rejected")

    def test_stale_evidence_rejected(self):
        stale = (NOW - timedelta(days=EVIDENCE_MAX_AGE_DAYS + 1)).isoformat()
        result = evaluate_creator_evidence(valid_evidence(timestamp=stale), now=NOW)
        self.assertIn("STALE_EVIDENCE", result.reasons)

    def test_boundary_freshness_accepted(self):
        edge = (NOW - timedelta(days=EVIDENCE_MAX_AGE_DAYS)).isoformat()
        result = evaluate_creator_evidence(valid_evidence(timestamp=edge), now=NOW)
        self.assertNotIn("STALE_EVIDENCE", result.reasons)
        self.assertEqual(result.status, "qualified")

    def test_determinism(self):
        payload = valid_evidence(audience_count=19999)
        first = evaluate_creator_evidence(payload, now=NOW)
        second = evaluate_creator_evidence(dict(payload), now=NOW)
        self.assertEqual(first.to_dict(), second.to_dict())
        self.assertEqual(first.reasons, sorted(first.reasons))

    def test_dataclass_input(self):
        evidence = CreatorEvidence(
            platform="tiktok",
            profile="https://tiktok.com/@example",
            audience_type="followers",
            audience_count=30000,
            evidence_url="https://tiktok.com/@example",
            evidence_source="profile page",
            timestamp=(NOW - timedelta(days=1)).isoformat(),
        )
        result = evaluate_creator_evidence(evidence, now=NOW)
        self.assertEqual(result.status, "qualified")

    def test_score_gate_integration(self):
        payload = valid_evidence()
        rejected = qualify_creator_with_evidence(0.10, payload, now=NOW)
        self.assertEqual(rejected.status, "rejected")
        self.assertIn("BELOW_THRESHOLD", rejected.reasons)
        passed = qualify_creator_with_evidence(0.90, payload, now=NOW)
        self.assertEqual(passed.status, "qualified")

    def test_evidence_gate_runs_first(self):
        bad = valid_evidence(audience_count=5)
        result = qualify_creator_with_evidence(0.99, bad, now=NOW)
        self.assertEqual(result.status, "rejected")
        self.assertIn("BELOW_THRESHOLD", result.reasons)

    def test_audience_isolation(self):
        result = evaluate_creator_evidence(valid_evidence(), now=NOW)
        d = result.to_dict()
        # Gate result must never carry commercial-proof keys.
        for forbidden in (
            "buyer_intent",
            "conversion",
            "conversion_rate",
            "revenue",
            "pmf",
            "product_market_fit",
        ):
            self.assertNotIn(forbidden, d)
        self.assertIn("audience_evidence_is_not_intent", result.isolation_note)
        # Guard raises if a caller merges forbidden keys.
        with self.assertRaises(ValueError):
            assert_audience_isolation({**d, "buyer_intent": 0.9})
        with self.assertRaises(ValueError):
            assert_audience_isolation({**d, "revenue": 100})


if __name__ == "__main__":
    unittest.main()
