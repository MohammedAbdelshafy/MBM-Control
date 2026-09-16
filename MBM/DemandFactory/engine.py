from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from .models import ConvictionAssessment, ConvictionGateResult, Decision, DemandSignal, Opportunity
from .quality import ProductQualityContract, validate_quality_contract


@dataclass(slots=True)
class FactoryResult:
    status: str
    opportunity_id: str | None
    decision: Decision | None
    diagnostics: dict


class DemandFactory:
    """Deterministic decision layer above existing MBM discovery/sales/build systems.

    Safe by default: it proposes actions and does not send outreach, charge customers,
    mutate a CRM, or publish products. Integrators can execute an approved action.
    """

    MIN_EVIDENCE = 0.35
    MIN_CONFIDENCE = 0.40
    MIN_EXPECTED_VALUE = 0.25
    CONVICTION_THRESHOLD = 0.72
    GATE_THRESHOLD = 0.60

    def evaluate(
        self,
        opportunity: Opportunity,
        signals: list[DemandSignal],
        *,
        armed: bool = False,
    ) -> FactoryResult:
        self._hydrate_from_signals(opportunity, signals)
        score = opportunity.score()

        rationale = {
            "demand_signal_count": len(signals),
            "evidence_levels": sorted({s.evidence_level for s in signals}),
            "expected_value": opportunity.expected_value,
            "confidence": opportunity.confidence,
            "armed": armed,
        }

        if not signals or opportunity.evidence_quality < self.MIN_EVIDENCE:
            decision = self._decision(
                opportunity,
                "validate_demand",
                rationale,
                "Demand evidence is insufficient for product construction.",
                ["collect at least 3 independent signals", "seek explicit request or observed purchase"],
                ["no new evidence after validation cycle"],
            )
            opportunity.state = "discovered"
            return FactoryResult("needs_validation", opportunity.opportunity_id, decision, {"score": score})

        if opportunity.confidence < self.MIN_CONFIDENCE or score < self.MIN_EXPECTED_VALUE:
            decision = self._decision(
                opportunity,
                "validate_demand",
                rationale,
                "Evidence exists, but expected commercial value is not yet strong enough to build.",
                ["test a low-cost offer", "measure click/reply/preorder intent"],
                ["validation fails to beat minimum conversion threshold"],
            )
            opportunity.state = "discovered"
            return FactoryResult("test_first", opportunity.opportunity_id, decision, {"score": score})

        action = self._next_action(opportunity)
        decision = self._decision(
            opportunity,
            action,
            rationale,
            f"Opportunity passed evidence and commercial gates; next action is {action}.",
            ["execute one controlled experiment", "record outcome", "re-score from observed data"],
            ["unit economics become negative", "quality gate fails", "no meaningful traction after test window"],
        )
        opportunity.state = {
            "build_product": "ready_to_build",
            "qa_product": "ready_to_launch",
            "launch_experiment": "ready_to_launch",
            "scale_winner": "scaling",
        }.get(action, opportunity.state)
        return FactoryResult("action_ready", opportunity.opportunity_id, decision, {"score": score})

    def assess_conviction(self, opportunity: Opportunity, conviction: ConvictionAssessment) -> ConvictionGateResult:
        scores = conviction.scores()
        passed = [name for name, value in scores.items() if value >= self.GATE_THRESHOLD]
        failed = [name for name, value in scores.items() if value < self.GATE_THRESHOLD]
        score = sum(scores.values()) / len(scores) if scores else 0.0

        if conviction.claim_integrity < self.GATE_THRESHOLD:
            return ConvictionGateResult(
                status="blocked",
                score=score,
                passed_gates=passed,
                failed_gates=failed,
                next_action="complete_proof",
                reasons=["claim_integrity_below_threshold"],
            )

        # A weak critical gate must never be averaged away by unrelated strong gates.
        # The overall threshold still matters as a quality signal, but every dimension
        # must clear the minimum gate before launch can proceed.
        if failed or score < self.CONVICTION_THRESHOLD:
            priority = min(
                failed,
                key=lambda name: scores[name] if name in scores else 1.0,
                default=min(scores, key=scores.get) if scores else "relevance",
            )
            action_map = {
                "relevance": "repair_offer",
                "outcome_clarity": "repair_offer",
                "proof": "complete_proof",
                "risk_reduction": "repair_offer",
                "purchase_friction": "repair_offer",
                "creative_readiness": "complete_creative",
                "personalization": "repair_offer",
                "trust": "complete_proof",
                "usage_readiness": "qa_product",
                "claim_integrity": "complete_proof",
            }
            status = "blocked" if conviction.claim_integrity < self.GATE_THRESHOLD else "repair"
            return ConvictionGateResult(
                status=status,
                score=score,
                passed_gates=passed,
                failed_gates=failed,
                next_action=action_map.get(priority, "repair_offer"),
                reasons=[f"weak_gate:{priority}"] if failed else ["overall_conviction_below_threshold"],
            )

        return ConvictionGateResult(
            status="ready",
            score=score,
            passed_gates=passed,
            failed_gates=failed,
            next_action="launch_experiment",
            reasons=["all_critical_conviction_dimensions_passed"],
        )

    def evaluate_full(
        self,
        opportunity: Opportunity,
        signals: list[DemandSignal],
        conviction: ConvictionAssessment,
        quality: ProductQualityContract,
        *,
        armed: bool = False,
    ) -> FactoryResult:
        base = self.evaluate(opportunity, signals, armed=armed)
        if base.status in {"needs_validation", "test_first"}:
            return base

        quality_failures = validate_quality_contract(quality)
        if quality_failures:
            decision = self._decision(
                opportunity,
                "qa_product",
                {"commercial_score": base.diagnostics["score"], "quality_failures": quality_failures},
                "Commercial opportunity exists, but the product does not yet satisfy the quality contract.",
                ["resolve every quality-contract failure", "re-run full evaluation"],
                ["quality cannot be substantiated without unsupported claims"],
            )
            return FactoryResult("quality_blocked", opportunity.opportunity_id, decision, {**base.diagnostics, "quality_failures": quality_failures})

        conviction_result = self.assess_conviction(opportunity, conviction)
        if conviction_result.status != "ready":
            decision = self._decision(
                opportunity,
                conviction_result.next_action,
                {"commercial_score": base.diagnostics["score"], "conviction": conviction_result.score},
                "Commercial gates passed, but consumer conviction still has repair work.",
                [f"resolve {gate}" for gate in conviction_result.failed_gates],
                ["do not launch while a critical conviction gate is below threshold"],
            )
            return FactoryResult("conviction_blocked", opportunity.opportunity_id, decision, {
                **base.diagnostics,
                "conviction": {
                    "status": conviction_result.status,
                    "score": conviction_result.score,
                    "passed_gates": conviction_result.passed_gates,
                    "failed_gates": conviction_result.failed_gates,
                },
            })

        action = self._next_action_after_conviction(opportunity)
        decision = self._decision(
            opportunity,
            action,
            {"commercial_score": base.diagnostics["score"], "conviction": conviction_result.score},
            "Evidence, economics, product quality, and consumer-conviction gates passed.",
            ["launch a controlled experiment", "attribute every conversion", "feed outcomes back into scoring"],
            ["negative unit economics", "quality regression", "meaningful traction absent after the test window"],
        )
        return FactoryResult("launch_ready", opportunity.opportunity_id, decision, {
            **base.diagnostics,
            "conviction": {
                "status": conviction_result.status,
                "score": conviction_result.score,
                "passed_gates": conviction_result.passed_gates,
                "failed_gates": conviction_result.failed_gates,
            },
        })

    def _hydrate_from_signals(self, opportunity: Opportunity, signals: list[DemandSignal]) -> None:
        if not signals:
            return
        opportunity.evidence_ids = [s.signal_id for s in signals]
        opportunity.demand_strength = self._mean(s.engagement for s in signals)
        opportunity.buyer_intent = self._mean(s.purchase_intent for s in signals)
        opportunity.evidence_quality = min(1.0, sum(s.evidence_weight for s in signals) / max(1, len(signals)))
        opportunity.pain_intensity = max(
            opportunity.pain_intensity,
            self._mean(float(s.metadata.get("pain_intensity", 0.5)) for s in signals),
        )
        opportunity.audience_access = max(
            opportunity.audience_access,
            self._mean(float(s.metadata.get("audience_access", 0.5)) for s in signals),
        )

    @staticmethod
    def _mean(values) -> float:
        items = list(values)
        return sum(items) / len(items) if items else 0.0

    @staticmethod
    def _next_action(opportunity: Opportunity) -> str:
        if opportunity.state == "ready_to_launch":
            return "launch_experiment"
        if opportunity.metadata.get("product_exists"):
            return "launch_experiment"
        if opportunity.metadata.get("prototype_exists"):
            return "qa_product"
        return "build_product"

    @staticmethod
    def _next_action_after_conviction(opportunity: Opportunity) -> str:
        if opportunity.metadata.get("product_exists"):
            return "launch_experiment"
        return "build_product"

    @staticmethod
    def _decision(
        opportunity: Opportunity,
        action: str,
        rationale: dict,
        summary: str,
        validation_plan: list[str],
        kill_conditions: list[str],
    ) -> Decision:
        return Decision(
            decision_id=f"dec-{uuid4().hex[:12]}",
            opportunity_id=opportunity.opportunity_id,
            action=action,
            rationale={"summary": summary, **rationale},
            expected_value=opportunity.expected_value,
            confidence=opportunity.confidence,
            validation_plan=validation_plan,
            kill_conditions=kill_conditions,
            owner="system",
        )


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
