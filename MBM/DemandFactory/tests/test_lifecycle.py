"""Deterministic tests for Factory lifecycle controller (#33)."""

import unittest

from MBM.DemandFactory.lifecycle import (
    MAX_QA_RETRIES,
    ReleaseManifest,
    RetryTracker,
    activation_mode,
    activation_prerequisites,
    can_publish,
    run_qa,
    should_schedule_run,
    transition,
    validate_release_manifest,
)


def good_manifest(**overrides):
    base = {
        "opportunity_id": "opp-1",
        "product_id": "prod-1",
        "offer_id": "offer-1",
        "proof_assets": ["demo-1"],
        "delivery_assets": ["kit.zip"],
        "checkout_rail": "whop",
        "evidence_ids": ["sig-1"],
        "qa_result": "passed",
        "conviction_status": "ready",
        "commercial_score": 1.2,
        "confidence": 0.8,
    }
    base.update(overrides)
    return ReleaseManifest(**base)


class LifecycleTests(unittest.TestCase):
    def test_happy_path_transitions(self):
        stage = "DISCOVERED"
        for event, expected in [
            ("research_complete", "RESEARCHED"),
            ("score_complete", "SCORED"),
            ("strategy_complete", "STRATEGY_READY"),
            ("build_approved", "BUILD_READY"),
            ("build_complete", "BUILDING"),
            ("qa_pass", "QA_PASSED"),
            ("package_complete", "PACKAGE_READY"),
            ("release_approved", "RELEASE_CANDIDATE"),
            ("release_complete", "RELEASED"),
        ]:
            stage = transition(stage, event)
            self.assertEqual(stage, expected)

    def test_illegal_transition_fail_closed(self):
        with self.assertRaises(ValueError):
            transition("DISCOVERED", "release_complete")
        with self.assertRaises(ValueError):
            transition("RELEASED", "retry")

    def test_unknown_stage_fail_closed(self):
        with self.assertRaises(ValueError):
            transition("MYSTERY", "kill")

    def test_qa_failed_retry_path(self):
        self.assertEqual(transition("BUILDING", "qa_fail"), "QA_FAILED")
        self.assertEqual(transition("QA_FAILED", "retry"), "BUILDING")
        self.assertEqual(transition("QA_FAILED", "quarantine"), "QUARANTINED")
        self.assertEqual(transition("QUARANTINED", "retry"), "BUILDING")

    def test_qa_aggregation(self):
        qa = run_qa(
            quality_failures=[],
            conviction_status="ready",
            evidence_ids=["sig-1"],
            evidence_quality=0.8,
            commercial_score=1.0,
            confidence=0.8,
        )
        self.assertTrue(qa.passed)
        bad = run_qa(
            quality_failures=["missing_proof_inventory"],
            conviction_status="repair",
            evidence_ids=[],
            evidence_quality=0.1,
            commercial_score=0.01,
            confidence=0.1,
        )
        self.assertFalse(bad.passed)
        self.assertIn("missing_proof_inventory", bad.failures)
        self.assertIn("qa_missing_evidence", bad.failures)

    def test_manifest_validation(self):
        self.assertEqual(validate_release_manifest(good_manifest()), [])
        bad = validate_release_manifest(good_manifest(proof_assets=[], qa_result="failed"))
        self.assertIn("manifest_missing_proof_assets", bad)
        self.assertIn("manifest_qa_not_passed", bad)
        empty = validate_release_manifest(ReleaseManifest())
        self.assertIn("manifest_missing_opportunity_id", empty)

    def test_failed_gates_cannot_publish(self):
        qa = run_qa(
            quality_failures=[],
            conviction_status="ready",
            evidence_ids=["sig-1"],
            evidence_quality=0.8,
            commercial_score=1.0,
            confidence=0.8,
        )
        # Not armed -> denied.
        allowed, reasons = can_publish(
            qa=qa,
            manifest_failures=[],
            mode="DRY_RUN",
            approval={"approved": True, "approver": "human"},
        )
        self.assertFalse(allowed)
        self.assertTrue(any("activation_not_armed" in r for r in reasons))
        # No approval -> denied even when armed.
        allowed2, reasons2 = can_publish(
            qa=qa, manifest_failures=[], mode="ARMED", approval=None
        )
        self.assertFalse(allowed2)
        self.assertIn("approval_missing", reasons2)
        # QA failed -> denied even when armed+approved.
        bad_qa = run_qa(
            quality_failures=["missing_proof_inventory"],
            conviction_status="ready",
            evidence_ids=["sig-1"],
            evidence_quality=0.8,
            commercial_score=1.0,
            confidence=0.8,
        )
        allowed3, _ = can_publish(
            qa=bad_qa, manifest_failures=[], mode="ARMED",
            approval={"approved": True, "approver": "human"},
        )
        self.assertFalse(allowed3)
        # All green -> allowed.
        allowed4, reasons4 = can_publish(
            qa=qa, manifest_failures=[], mode="ARMED",
            approval={"approved": True, "approver": "human"},
        )
        self.assertTrue(allowed4)
        self.assertEqual(reasons4, [])

    def test_retry_limits_and_quarantine(self):
        tracker = RetryTracker()
        for _ in range(MAX_QA_RETRIES - 1):
            self.assertEqual(tracker.record_failure(), "retry")
            self.assertFalse(tracker.quarantined)
        self.assertEqual(tracker.record_failure(), "quarantine")
        self.assertTrue(tracker.quarantined)

    def test_activation_guarded(self):
        self.assertEqual(activation_mode(armed_flag=False, env={}), "OFF")
        # Half-armed stays DRY_RUN (fail-closed).
        self.assertEqual(activation_mode(armed_flag=True, env={}), "DRY_RUN")
        self.assertEqual(activation_mode(armed_flag=False, env={"FACTORY_ARMED": "1"}), "DRY_RUN")
        self.assertEqual(
            activation_mode(armed_flag=True, env={"FACTORY_ARMED": "1"}), "ARMED"
        )
        self.assertIn("human_approval_recorded", activation_prerequisites("ARMED"))

    def test_scheduled_execution_guarded(self):
        allowed, _ = should_schedule_run("DRY_RUN")
        self.assertTrue(allowed)
        allowed_off, _ = should_schedule_run("OFF")
        self.assertTrue(allowed_off)
        blocked, reason = should_schedule_run("ARMED")
        self.assertFalse(blocked)
        self.assertIn("blocked", reason)

    def test_no_publish_invariant(self):
        # Even a perfect manifest cannot publish without ARMED+approval.
        qa = run_qa(
            quality_failures=[], conviction_status="ready", evidence_ids=["s"],
            evidence_quality=0.9, commercial_score=2.0, confidence=0.9,
        )
        for mode in ("OFF", "DRY_RUN"):
            allowed, _ = can_publish(
                qa=qa, manifest_failures=[], mode=mode,
                approval={"approved": True, "approver": "human"},
            )
            self.assertFalse(allowed)


if __name__ == "__main__":
    unittest.main()
