import unittest

from MBM.DemandFactory.conviction import evaluate_conviction


class ConvictionTests(unittest.TestCase):
    def test_missing_proof_and_checkout_cannot_launch(self):
        result = evaluate_conviction({
            "relevance": 0.95,
            "outcome_clarity": 0.95,
            "proof": 0.2,
            "risk_reduction": 0.8,
            "purchase_friction": 0.9,
            "creative_readiness": 0.9,
            "personalization": 0.7,
            "trust": 0.8,
            "usage_readiness": 0.8,
            "claims_verified": True,
            "proof_provenance": False,
            "delivery_assets": ["starter-kit.zip"],
        })
        self.assertFalse(result.launch_ready)
        self.assertIn("proof_weak", result.blockers)
        self.assertIn("proof_provenance_missing", result.blockers)
        self.assertIn("checkout_rail_missing", result.blockers)

    def test_complete_product_can_pass_conviction_gate(self):
        result = evaluate_conviction({
            "relevance": 0.95,
            "outcome_clarity": 0.95,
            "proof": 0.9,
            "risk_reduction": 0.85,
            "purchase_friction": 0.9,
            "creative_readiness": 0.9,
            "personalization": 0.8,
            "trust": 0.9,
            "usage_readiness": 0.9,
            "claims_verified": True,
            "proof_provenance": True,
            "checkout_rails": ["whop"],
            "delivery_assets": ["starter-kit.zip", "onboarding.md"],
        })
        self.assertTrue(result.launch_ready)
        self.assertEqual(result.blockers, [])
        self.assertGreaterEqual(result.score, 0.78)


if __name__ == "__main__":
    unittest.main()
