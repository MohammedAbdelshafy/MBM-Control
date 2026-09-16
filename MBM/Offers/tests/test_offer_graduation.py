"""Offer graduation: QUARANTINED -> VALIDATED -> RELEASE-CANDIDATE (Mission 15).

Graduates the P4 DFY Lead List Cleaner through the evidence-first path
using REAL execution evidence (cleaner run on the labeled demo set).
No market/ROI/testimonial claims. Publish remains human-gated:
the test proves can_publish is DENIED without approval — without
executing any external action.
"""

import importlib.util
import tempfile
import unittest
from pathlib import Path

from MBM.DemandFactory.lifecycle import (
    ReleaseManifest,
    can_publish,
    run_qa,
    transition,
    validate_release_manifest,
)
from MBM.Offers.offer_schema import ProductOffer, validate_offer

SERVICE_ROOT = Path(__file__).resolve().parents[3] / "productized-service" / "p4-lead-cleaner"
DEMO_CSV = SERVICE_ROOT / "demo" / "sample_lead_list.csv"


def _load_cleaner():
    spec = importlib.util.spec_from_file_location(
        "p4_clean_leads", SERVICE_ROOT / "clean_leads.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class OfferGraduationTests(unittest.TestCase):
    def test_p4_offer_graduates_to_release_candidate(self):
        self.assertTrue(DEMO_CSV.exists(), "p4 demo input must exist")
        with tempfile.TemporaryDirectory() as tmp:
            summary = _load_cleaner().run_cleaner(DEMO_CSV, job="graduation_probe", report_dir=Path(tmp))
        # REAL execution evidence (deterministic canonical gate).
        self.assertEqual(summary["total_records"], 11)
        evidence_ids = [
            f"p4-demo:{summary['generated_at']}",
            f"p4-demo:cleaned_csv:{Path(summary['cleaned_csv']).name}",
            "p4-demo:canonical_gate:dialer_verification_gate",
        ]
        offer = ProductOffer(
            offer_id="offer-p4-lead-cleaner",
            problem="lead lists contain duplicates, dead numbers, and suppressed phones",
            buyer_segment="agencies and closers running outbound",
            promise="return every input row classified VERIFIED/CALLABLE/NOT CALLABLE/DUPLICATE/SUPPRESSED by the canonical gate",
            format="dfy_report",
            price=499.0,
            proof_assets=[f"demo run {summary['job']}: {summary['total_records']} rows, "
                          f"{summary['status_counts']['CALLABLE']} callable"],
            evidence_ids=evidence_ids,
            evidence_level="explicit_request",
            limitations=["verification is syntactic+source-based, not live carrier ping",
                         "Bolivia country-code 591 and 555 patterns are never dialable"],
            checkout_rail="neteller",
            delivery_assets=["cleaned.csv", "summary.json", "report.md"],
            claims_text="Deterministic classification by the canonical verification gate.",
        )
        # VALIDATED
        self.assertEqual(validate_offer(offer), [])
        qa = run_qa(quality_failures=[], conviction_status="ready",
                    evidence_ids=evidence_ids, evidence_quality=0.8,
                    commercial_score=1.0, confidence=0.8)
        self.assertTrue(qa.passed)
        manifest = ReleaseManifest(
            opportunity_id="opp-p4", product_id="prod-p4-lead-cleaner",
            offer_id="offer-p4-lead-cleaner",
            proof_assets=list(offer.proof_assets),
            delivery_assets=list(offer.delivery_assets),
            checkout_rail="neteller", evidence_ids=evidence_ids,
            qa_result="passed", conviction_status="ready",
            commercial_score=1.0, confidence=0.8)
        self.assertEqual(validate_release_manifest(manifest), [])
        # RELEASE-CANDIDATE via deterministic lifecycle walk.
        stage = "DISCOVERED"
        for event in ("research_complete", "score_complete", "strategy_complete",
                      "build_approved", "build_complete", "qa_pass",
                      "package_complete", "release_approved"):
            stage = transition(stage, event)
        self.assertEqual(stage, "RELEASE_CANDIDATE")
        # Publish stays human-gated: denied without approval, no side effects.
        allowed, reasons = can_publish(
            qa=qa, manifest_failures=[], mode="ARMED", approval=None)
        self.assertFalse(allowed)
        self.assertIn("approval_missing", reasons)


if __name__ == "__main__":
    unittest.main()
