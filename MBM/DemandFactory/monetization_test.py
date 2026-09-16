import unittest

from MBM.DemandFactory.monetization import build_monetization_plan
from MBM.DemandFactory.models import Opportunity


class MonetizationTests(unittest.TestCase):
    def test_plan_is_blocked_without_real_delivery_and_proof(self):
        opportunity = Opportunity(
            opportunity_id="opp-1",
            problem="save time",
            buyer_segment="operators",
            distributor_type="direct",
            price_potential=97,
        )
        plan = build_monetization_plan(opportunity)
        self.assertFalse(plan.launch_ready)
        self.assertIn("proof_missing", plan.blockers)
        self.assertIn("delivery_assets_missing", plan.blockers)

    def test_plan_can_be_launch_ready_with_real_transaction_path(self):
        opportunity = Opportunity(
            opportunity_id="opp-2",
            problem="save time",
            buyer_segment="operators",
            distributor_type="direct",
            price_potential=97,
            metadata={
                "buyer_outcome": "produce a qualified lead list faster",
                "launch_price": 97,
                "proof_assets": ["verified workflow demo"],
                "delivery_assets": ["toolkit.zip", "onboarding.md"],
                "checkout_rails": ["whop"],
            },
        )
        plan = build_monetization_plan(opportunity)
        self.assertTrue(plan.launch_ready)
        self.assertEqual(plan.price, 97)
        self.assertEqual(plan.checkout_rails, ["whop"])


if __name__ == "__main__":
    unittest.main()
