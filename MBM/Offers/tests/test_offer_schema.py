"""Tests for evidence-first Revenue Offers (#64)."""

import unittest

from MBM.Offers.offer_schema import (
    ProductOffer,
    offer_readiness,
    validate_offer,
    validate_offer_end_to_end,
)


def good_offer(**overrides):
    base = {
        "offer_id": "offer-1",
        "problem": "estimating takes too long",
        "buyer_segment": "contractors",
        "promise": "produce a first estimate faster with a verified workflow",
        "format": "toolkit",
        "price": 149.0,
        "proof_assets": ["demo-1"],
        "evidence_ids": ["sig-1", "sig-2", "sig-3"],
        "evidence_level": "explicit_request",
        "limitations": ["supplier prices still require review"],
        "checkout_rail": "whop",
        "delivery_assets": ["toolkit.zip"],
        "claims_text": "Verified workflow demo included.",
    }
    base.update(overrides)
    return ProductOffer(**base)


class OfferSchemaTests(unittest.TestCase):
    def test_valid_offer_ready(self):
        self.assertEqual(validate_offer(good_offer()), [])
        self.assertTrue(offer_readiness(good_offer())["ready"])

    def test_missing_fields_fail(self):
        failures = validate_offer(ProductOffer())
        for code in (
            "offer_missing_id",
            "offer_missing_problem",
            "offer_missing_buyer_segment",
            "offer_missing_promise",
            "offer_missing_format",
            "offer_missing_price",
            "offer_missing_proof",
            "offer_missing_evidence",
            "offer_missing_limitations",
            "offer_missing_checkout_rail",
            "offer_missing_delivery",
        ):
            self.assertIn(code, failures)

    def test_fabricated_market_without_evidence_rejected(self):
        offer = good_offer(
            evidence_ids=[],
            evidence_level="hypothesis",
            proof_assets=[],
            claims_text="$2.74B market growing at 29.9% CAGR, 78% of marketing teams use AI video",
        )
        failures = validate_offer(offer)
        self.assertIn("FABRICATED_MARKET_DATA", failures)

    def test_fabricated_roi_savings_rejected(self):
        offer = good_offer(
            evidence_ids=[],
            evidence_level="hypothesis",
            proof_assets=[],
            claims_text="ROI 10x, savings 94-98% vs agency $500 per clip",
        )
        failures = validate_offer(offer)
        self.assertIn("FABRICATED_ROI", failures)
        self.assertIn("FABRICATED_SAVINGS", failures)

    def test_revenue_guarantee_requires_purchase_evidence(self):
        offer = good_offer(
            evidence_level="explicit_request",
            claims_text="Revenue $497/mo with money-back guarantee and testimonials ★★★★★",
        )
        failures = validate_offer(offer)
        # explicit_request is not purchase-level: revenue/testimonial/guarantee still blocked
        self.assertIn("FABRICATED_REVENUE", failures)
        self.assertIn("FABRICATED_TESTIMONIAL", failures)
        self.assertIn("FABRICATED_GUARANTEE", failures)

    def test_end_to_end_path(self):
        result = validate_offer_end_to_end(good_offer(), conviction_status="ready", qa_failures=[])
        self.assertTrue(result["ready"])
        self.assertEqual(result["execution"], "proposal_only_human_approval_required")
        blocked = validate_offer_end_to_end(
            good_offer(evidence_ids=[], evidence_level="hypothesis", proof_assets=[]),
            conviction_status="repair",
            qa_failures=["missing_proof_inventory"],
        )
        self.assertFalse(blocked["ready"])
        self.assertFalse(blocked["qa_passed"])

    def test_determinism(self):
        self.assertEqual(validate_offer(good_offer()), validate_offer(good_offer()))

    def test_legacy_offer_fails(self):
        # Legacy 01_ShortForm_Content_Engine.md style claims must FAIL.
        legacy = good_offer(
            evidence_ids=[],
            evidence_level="hypothesis",
            proof_assets=[],
            claims_text=(
                "$2.74B market growing at 29.9% CAGR. 78% of marketing teams already use AI video. "
                "ROI calculator savings 94-98%. 30-day money-back guarantee. $497/mo pricing plan."
            ),
        )
        failures = validate_offer(legacy)
        self.assertIn("FABRICATED_MARKET_DATA", failures)
        self.assertIn("FABRICATED_GUARANTEE", failures)


if __name__ == "__main__":
    unittest.main()
