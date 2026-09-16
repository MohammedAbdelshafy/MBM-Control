import unittest

from MBM.DemandFactory.models import Opportunity
from MBM.DemandFactory.monetization import build_monetization_plan
from MBM.DemandFactory.router import choose_revenue_route


class RevenueRouterTests(unittest.TestCase):
    def test_defaults_to_whop_when_configured(self):
        opportunity = Opportunity(
            opportunity_id="opp-whop",
            problem="lead qualification",
            buyer_segment="small agencies",
            distributor_type="affiliate",
            price_potential=149,
            metadata={
                "launch_price": 149,
                "buyer_outcome": "qualify leads faster",
                "proof_assets": ["workflow demo"],
                "delivery_assets": ["toolkit.zip"],
                "checkout_rails": ["whop"],
                "acquisition_channels": ["affiliate"],
            },
        )
        plan = build_monetization_plan(opportunity, product_name="Lead Qualification Kit")
        route = choose_revenue_route(opportunity, plan)
        self.assertEqual(route.rail, "whop")
        self.assertTrue(route.live_capability)
        self.assertEqual(route.next_action, "configure_whop_offer")

    def test_high_ticket_routes_to_dfy(self):
        opportunity = Opportunity(
            opportunity_id="opp-dfy",
            problem="custom automation",
            buyer_segment="service businesses",
            distributor_type="direct",
            price_potential=2500,
            metadata={
                "launch_price": 2500,
                "buyer_outcome": "deploy a tailored automation system",
                "proof_assets": ["case study"],
                "delivery_assets": ["implementation"],
                "checkout_rails": [],
                "acquisition_channels": ["direct"],
                "service": True,
            },
        )
        plan = build_monetization_plan(opportunity, product_name="AI Automation Sprint")
        route = choose_revenue_route(opportunity, plan)
        # Canonical: service-shaped / price>=1000 routes to high_ticket_dfy
        # (router.py). Previous assertion expected direct_sales, contradicting
        # the test name, router docstring, and PR #57 rail list.
        self.assertEqual(route.rail, "high_ticket_dfy")
        self.assertEqual(route.next_action, "prepare_dfy_sales_offer")

    def test_direct_sales_fallback(self):
        # Non-service, low-price, no whop/shopify/affiliate → direct_sales.
        opportunity = Opportunity(
            opportunity_id="opp-direct",
            problem="one-off cleanup",
            buyer_segment="local shops",
            distributor_type="direct",
            price_potential=150,
            metadata={
                "launch_price": 150,
                "buyer_outcome": "one-time cleanup",
                "proof_assets": ["checklist"],
                "delivery_assets": ["report.pdf"],
                "checkout_rails": [],
                "acquisition_channels": ["direct"],
            },
        )
        plan = build_monetization_plan(opportunity, product_name="Cleanup Sprint")
        route = choose_revenue_route(opportunity, plan)
        self.assertEqual(route.rail, "direct_sales")
        self.assertEqual(route.next_action, "prepare_direct_sales_pack")


if __name__ == "__main__":
    unittest.main()
