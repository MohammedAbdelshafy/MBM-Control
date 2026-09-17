import unittest

from .engine import DemandFactory
from .models import ConvictionAssessment, DemandSignal, Opportunity
from .quality import ProductQualityContract, validate_quality_contract


def complete_quality(evidence_level="observed_purchase"):
    return ProductQualityContract(
        outcome_statement="Produce a verified estimating workflow in minutes.",
        proof_inventory=["working demo", "observed purchase in adjacent market"],
        buyer_preview="Three screenshots and a sample output are provided before purchase.",
        usage_path=["download", "import", "run", "review"],
        objection_map=["Will this fit my workflow?", "Can I see an example?"],
        limitations=["Supplier prices still require review when no source exists."],
        qa_checks=["sample input", "broken input", "export", "mobile preview"],
        claim_evidence_level=evidence_level,
    )


class DemandFactoryTests(unittest.TestCase):
    def strong_opportunity(self):
        return Opportunity(
            "opp-strong",
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

    def strong_signals(self):
        return [
            DemandSignal("sig-1", "community", "pricing confusion", "explicit_request", engagement=0.9, purchase_intent=0.9, metadata={"pain_intensity": 0.9, "audience_access": 0.9}),
            DemandSignal("sig-2", "marketplace", "pricing confusion", "observed_purchase", engagement=0.9, purchase_intent=0.9, metadata={"pain_intensity": 0.9, "audience_access": 0.9}),
            DemandSignal("sig-3", "search", "pricing confusion", "repeated_signal", engagement=0.8, purchase_intent=0.8, metadata={"pain_intensity": 0.8, "audience_access": 0.8}),
        ]

    def test_weak_evidence_needs_validation(self):
        opportunity = Opportunity("opp-1", "pricing confusion", "contractors", "creator")
        signals = [DemandSignal("sig-1", "instagram", "pricing confusion", "single_signal", engagement=0.7, purchase_intent=0.2)]
        result = DemandFactory().evaluate(opportunity, signals)
        self.assertEqual(result.status, "needs_validation")
        self.assertEqual(result.decision.action, "validate_demand")

    def test_strong_evidence_can_build(self):
        result = DemandFactory().evaluate(self.strong_opportunity(), self.strong_signals())
        self.assertEqual(result.status, "action_ready")
        self.assertEqual(result.decision.action, "build_product")
        self.assertGreater(result.diagnostics["score"], 0.25)

    def test_low_conviction_repairs_weakest_gate(self):
        assessment = DemandFactory().assess_conviction(
            self.strong_opportunity(),
            ConvictionAssessment(
                relevance=0.9,
                outcome_clarity=0.9,
                proof=0.4,
                risk_reduction=0.9,
                purchase_friction=0.8,
                creative_readiness=0.8,
                personalization=0.8,
                trust=0.7,
                usage_readiness=0.8,
                claim_integrity=0.9,
            ),
        )
        self.assertEqual(assessment.status, "repair")
        self.assertEqual(assessment.next_action, "complete_proof")

    def test_claim_integrity_blocks_launch(self):
        assessment = DemandFactory().assess_conviction(
            self.strong_opportunity(),
            ConvictionAssessment(
                relevance=1.0,
                outcome_clarity=1.0,
                proof=1.0,
                risk_reduction=1.0,
                purchase_friction=1.0,
                creative_readiness=1.0,
                personalization=1.0,
                trust=1.0,
                usage_readiness=1.0,
                claim_integrity=0.3,
            ),
        )
        self.assertEqual(assessment.status, "blocked")
        self.assertEqual(assessment.next_action, "complete_proof")

    def test_complete_quality_contract_passes(self):
        self.assertEqual(validate_quality_contract(complete_quality()), [])

    def test_incomplete_quality_contract_fails(self):
        failures = validate_quality_contract(ProductQualityContract())
        self.assertIn("missing_proof_inventory", failures)
        self.assertIn("missing_buyer_preview", failures)

    def test_full_evaluation_blocks_low_conviction(self):
        result = DemandFactory().evaluate_full(
            self.strong_opportunity(),
            self.strong_signals(),
            ConvictionAssessment(
                relevance=0.9, outcome_clarity=0.9, proof=0.9, risk_reduction=0.9,
                purchase_friction=0.9, creative_readiness=0.3, personalization=0.9,
                trust=0.9, usage_readiness=0.9, claim_integrity=0.9,
            ),
            complete_quality(),
        )
        self.assertEqual(result.status, "conviction_blocked")
        self.assertEqual(result.decision.action, "complete_creative")

    def test_full_evaluation_is_launch_ready(self):
        result = DemandFactory().evaluate_full(
            self.strong_opportunity(),
            self.strong_signals(),
            ConvictionAssessment(
                relevance=0.9, outcome_clarity=0.9, proof=0.9, risk_reduction=0.9,
                purchase_friction=0.9, creative_readiness=0.9, personalization=0.9,
                trust=0.9, usage_readiness=0.9, claim_integrity=0.95,
            ),
            complete_quality(),
        )
        self.assertEqual(result.status, "launch_ready")
        self.assertIn(result.decision.action, {"build_product", "launch_experiment"})


if __name__ == "__main__":
    unittest.main()
