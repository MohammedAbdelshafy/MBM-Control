import unittest

from .engine import DemandFactory
from .models import DemandSignal, Opportunity


class DemandFactoryTests(unittest.TestCase):
    def test_weak_evidence_needs_validation(self):
        opportunity = Opportunity("opp-1", "pricing confusion", "contractors", "creator")
        signals = [
            DemandSignal(
                "sig-1",
                "instagram",
                "pricing confusion",
                "single_signal",
                engagement=0.7,
                purchase_intent=0.2,
            )
        ]
        result = DemandFactory().evaluate(opportunity, signals)
        self.assertEqual(result.status, "needs_validation")
        self.assertEqual(result.decision.action, "validate_demand")

    def test_strong_evidence_can_build(self):
        opportunity = Opportunity(
            "opp-2",
            "pricing confusion",
            "contractors",
            "creator",
            pain_intensity=0.9,
            distribution_probability=0.8,
            price_potential=0.8,
            gross_margin=0.9,
            repeat_potential=0.7,
            expansion_potential=0.8,
            production_cost=0.1,
        )
        signals = [
            DemandSignal(
                "sig-1",
                "community",
                "pricing confusion",
                "explicit_request",
                engagement=0.9,
                purchase_intent=0.9,
                metadata={"pain_intensity": 0.9, "audience_access": 0.9},
            ),
            DemandSignal(
                "sig-2",
                "marketplace",
                "pricing confusion",
                "observed_purchase",
                engagement=0.9,
                purchase_intent=0.9,
                metadata={"pain_intensity": 0.9, "audience_access": 0.9},
            ),
            DemandSignal(
                "sig-3",
                "search",
                "pricing confusion",
                "repeated_signal",
                engagement=0.8,
                purchase_intent=0.8,
                metadata={"pain_intensity": 0.8, "audience_access": 0.8},
            ),
        ]
        result = DemandFactory().evaluate(opportunity, signals)
        self.assertEqual(result.status, "action_ready")
        self.assertEqual(result.decision.action, "build_product")
        self.assertGreater(opportunity.confidence, 0.4)


if __name__ == "__main__":
    unittest.main()
