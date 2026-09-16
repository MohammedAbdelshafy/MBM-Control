"""End-to-end Factory smoke: TASK -> RESULT through real deterministic code.

Stages exercised (no simulation, no external side effects):
DISCOVERY (radar_slice_a) -> SCORE (creator_evidence_gate + dialer-shaped QA)
-> STRATEGY (offer_validation) -> QA (lifecycle.run_qa)
-> PACKAGE (release manifest validate) -> RELEASE gate (can_publish, DRY_RUN denied)
-> MEASURE/LEARN (capability evidence built) -> AUDIT (result dict).
"""

import unittest
from datetime import datetime, timedelta, timezone

from jarvis_control_plane.capability_registry import build_capability_registry
from jarvis_control_plane.factory_routing import build_evidence, route_capability
from MBM.ContecRadar.slice_a import run_slice_a
from MBM.DemandFactory.creator_gate import evaluate_creator_evidence
from MBM.DemandFactory.lifecycle import (
    ReleaseManifest,
    can_publish,
    run_qa,
    validate_release_manifest,
)
from MBM.Offers.offer_schema import ProductOffer, validate_offer


class FactoryEndToEndTests(unittest.TestCase):
    def test_task_to_result(self):
        now = datetime(2026, 9, 10, 12, 0, 0, tzinfo=timezone.utc)
        # DISCOVERY
        radar = run_slice_a([
            {"signal_id": "e2e-1", "title": "AI estimating workflow",
             "body": "contractor estimating pain, verified workflow demo",
             "source": "offline_fixture"},
        ])
        self.assertGreaterEqual(len(radar.opportunities), 1)
        # CAPABILITY + AGENT + SKILL selection is deterministic routing:
        spec, decision = route_capability("radar_slice_a", "DISCOVER")
        self.assertEqual(spec.capability, "radar_slice_a")
        # SCORE: creator gate
        gate = evaluate_creator_evidence(
            {"platform": "youtube", "profile": "https://youtube.com/@e2e",
             "audience_type": "subscribers", "audience_count": 25000,
             "evidence_url": "https://youtube.com/@e2e/about",
             "evidence_source": "channel page",
             "timestamp": (now - timedelta(days=3)).isoformat()},
            now=now,
        )
        self.assertEqual(gate.status, "qualified")
        # STRATEGY: offer validation
        offer = ProductOffer(
            offer_id="offer-e2e", problem="estimating takes too long",
            buyer_segment="contractors",
            promise="produce a first estimate faster with a verified workflow",
            format="toolkit", price=149.0, proof_assets=["demo-1"],
            evidence_ids=["e2e-1"], evidence_level="explicit_request",
            limitations=["supplier prices require review"],
            checkout_rail="whop", delivery_assets=["toolkit.zip"],
            claims_text="Verified workflow demo included.",
        )
        self.assertEqual(validate_offer(offer), [])
        # QA + PACKAGE
        qa = run_qa(quality_failures=[], conviction_status="ready",
                    evidence_ids=["e2e-1"], evidence_quality=0.8,
                    commercial_score=1.0, confidence=0.8)
        self.assertTrue(qa.passed)
        manifest = ReleaseManifest(
            opportunity_id="opp-e2e", product_id="prod-e2e", offer_id="offer-e2e",
            proof_assets=["demo-1"], delivery_assets=["toolkit.zip"],
            checkout_rail="whop", evidence_ids=["e2e-1"],
            qa_result="passed", conviction_status="ready",
            commercial_score=1.0, confidence=0.8,
        )
        self.assertEqual(validate_release_manifest(manifest), [])
        # RELEASE gate stays denied in DRY_RUN (no-publish invariant holds e2e)
        allowed, reasons = can_publish(
            qa=qa, manifest_failures=[], mode="DRY_RUN",
            approval={"approved": True, "approver": "human"})
        self.assertFalse(allowed)
        # MEASURE/LEARN + AUDIT evidence
        evidence = build_evidence(
            spec=spec, actor="e2e-test", inputs={"signals": 1},
            outputs={"opportunities": len(radar.opportunities)},
            approval=None, policy_decision=decision, success=True,
            state="MEASURED")
        self.assertEqual(evidence.state, "MEASURED")
        self.assertTrue(evidence.success)
        # Registry coherence: every routed capability is known (DENY otherwise)
        self.assertGreaterEqual(len(build_capability_registry()), 20)


if __name__ == "__main__":
    unittest.main()
