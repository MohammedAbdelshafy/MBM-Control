from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from .models import Decision, DemandSignal, Opportunity


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
