import unittest

from .revenue_bridge import RevenueEvent, attribution_key, build_revenue_event


class RevenueBridgeTests(unittest.TestCase):
    def test_observed_purchase_requires_real_transaction_fields(self):
        event = build_revenue_event(
            transaction_id="txn_1",
            opportunity_id="opp_1",
            offer_id="offer_1",
            product_id="product_1",
            distributor_id="creator_1",
            channel="creator",
            checkout_reference="checkout_1",
            gross_revenue=97.0,
            source="whop",
            currency="USD",
        )
        self.assertEqual(event.evidence_level, "observed_purchase")
        self.assertEqual(event.gross_revenue, 97.0)

    def test_invalid_event_cannot_be_serialized_as_revenue(self):
        event = RevenueEvent(
            transaction_id="",
            opportunity_id="opp_1",
            offer_id="offer_1",
            product_id="product_1",
            gross_revenue=0,
            source="whop",
        )
        with self.assertRaises(ValueError):
            event.to_dict()

    def test_attribution_key_is_deterministic(self):
        self.assertEqual(
            attribution_key(
                opportunity_id="opp_1",
                offer_id="offer_1",
                product_id="product_1",
                distributor_id="creator_1",
                channel="creator",
            ),
            "revenue:opp_1:offer_1:product_1:creator_1:creator",
        )


if __name__ == "__main__":
    unittest.main()
