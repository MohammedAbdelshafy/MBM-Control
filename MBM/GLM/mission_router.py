#!/usr/bin/env python3
"""
GLM Swarm Mission Router & Priority Engine
==========================================
Calculates priority scores using the canonical business formula:
  Priority = Business Impact (1-10) * Revenue Impact (1-10) * Probability of Success (0.1-1.0) * Urgency (1-5)

Enforces the Authoritative 5D Revenue Gate (Score >= 70.0 / 100):
  1. Business Value (0-20)
  2. Revenue Potential (0-20)
  3. Customer Urgency (0-15)
  4. Implementation Fit (0-15)
  5. Reusability (0-10)
  6. Time To Value (0-10)
  7. Risk Reduction (0-10)
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from MBM.GLM.agent_registry import GLMRole, ModelRoutingTier


REVENUE_GATE_THRESHOLD: float = 70.0


class MissionCategory(str):
    CRITICAL_PRODUCTION_BUG = "CRITICAL_PRODUCTION_BUG"
    REVENUE_BLOCKER = "REVENUE_BLOCKER"
    DATA_INTEGRITY = "DATA_INTEGRITY"
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    RELIABILITY = "RELIABILITY"
    DEVOPS = "DEVOPS"
    GTM_REVENUE = "GTM_REVENUE"
    SOCIAL_INTELLIGENCE = "SOCIAL_INTELLIGENCE"
    DIALER_COCKPIT = "DIALER_COCKPIT"
    DEVELOPER_PRODUCTIVITY = "DEVELOPER_PRODUCTIVITY"
    DOCUMENTATION = "DOCUMENTATION"


class RevenueGateBreakdown(BaseModel):
    business_value: float = Field(..., ge=0.0, le=20.0)
    revenue_potential: float = Field(..., ge=0.0, le=20.0)
    customer_urgency: float = Field(..., ge=0.0, le=15.0)
    implementation_fit: float = Field(..., ge=0.0, le=15.0)
    reusability: float = Field(..., ge=0.0, le=10.0)
    time_to_value: float = Field(..., ge=0.0, le=10.0)
    risk_reduction: float = Field(..., ge=0.0, le=10.0)
    total_score: float = Field(..., ge=0.0, le=100.0)
    passed: bool
    verdict: str  # "APPROVED", "DEFERRED", "REJECTED"
    rationale: str


def calculate_5d_revenue_gate(
    business_impact: float,
    revenue_impact: float,
    urgency: float,
    probability_of_success: float,
    category: str = "DEVELOPER_PRODUCTIVITY",
    estimated_complexity: str = "MEDIUM",
    risk_level: str = "LOW",
    breakdown_override: Optional[RevenueGateBreakdown] = None,
) -> RevenueGateBreakdown:
    """Calculates canonical 5D Revenue Gate score (/100) per docs/AGENTIC_5D_REVENUE_GATE.md."""
    if breakdown_override is not None:
        return breakdown_override

    # 1. Business Value (0-20)
    bv = round(min(20.0, max(0.0, (float(business_impact) / 10.0) * 20.0)), 2)

    # 2. Revenue Potential (0-20)
    rp = round(min(20.0, max(0.0, (float(revenue_impact) / 10.0) * 20.0)), 2)

    # 3. Customer Urgency (0-15)
    cu = round(min(15.0, max(0.0, (float(urgency) / 5.0) * 15.0)), 2)

    # 4. Implementation Fit (0-15)
    fit = round(min(15.0, max(0.0, float(probability_of_success) * 15.0)), 2)

    # 5. Reusability (0-10)
    cat_upper = str(category).upper()
    if any(k in cat_upper for k in ["DATA_INTEGRITY", "REVENUE_BLOCKER", "GTM_REVENUE"]):
        reu = 10.0
    elif any(k in cat_upper for k in ["SECURITY", "DIALER", "SOCIAL", "PERFORMANCE", "RELIABILITY"]):
        reu = 8.0
    else:
        reu = 6.0

    # 6. Time To Value (0-10)
    comp_upper = str(estimated_complexity).upper()
    if comp_upper == "LOW":
        ttv = 10.0
    elif comp_upper == "MEDIUM":
        ttv = 8.0
    else:
        ttv = 5.0

    # 7. Risk Reduction (0-10)
    risk_upper = str(risk_level).upper()
    if risk_upper == "LOW":
        rr = 10.0
    elif risk_upper == "MEDIUM":
        rr = 7.0
    else:
        rr = 4.0

    total = round(min(100.0, bv + rp + cu + fit + reu + ttv + rr), 2)
    passed = total >= REVENUE_GATE_THRESHOLD

    if total >= REVENUE_GATE_THRESHOLD:
        verdict = "APPROVED"
        rationale = f"Score {total:.1f} >= {REVENUE_GATE_THRESHOLD}: Cleared 5D Revenue Gate for mission routing."
    elif total >= 50.0:
        verdict = "DEFERRED"
        rationale = f"Score {total:.1f} < {REVENUE_GATE_THRESHOLD}: Insufficient commercial urgency. Deferred until revenue proof exists."
    else:
        verdict = "REJECTED"
        rationale = f"Score {total:.1f} < 50.0: Sub-critical business value and negligible direct monetization. Rejected."

    return RevenueGateBreakdown(
        business_value=bv,
        revenue_potential=rp,
        customer_urgency=cu,
        implementation_fit=fit,
        reusability=reu,
        time_to_value=ttv,
        risk_reduction=rr,
        total_score=total,
        passed=passed,
        verdict=verdict,
        rationale=rationale,
    )


class EngineeringMission(BaseModel):
    mission_id: str
    title: str
    target_repo: str
    target_paths: List[str]
    category: str
    assigned_role: GLMRole
    routing_tier: ModelRoutingTier
    business_impact: float = Field(..., ge=1.0, le=10.0)
    revenue_impact: float = Field(..., ge=1.0, le=10.0)
    probability_of_success: float = Field(..., ge=0.1, le=1.0)
    urgency: float = Field(..., ge=1.0, le=5.0)
    problem_statement: str
    recommended_fix: str
    risk_level: str = "LOW"
    estimated_complexity: str = "MEDIUM"
    status: str = "PENDING"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    revenue_gate_override: Optional[RevenueGateBreakdown] = None

    @property
    def revenue_gate(self) -> RevenueGateBreakdown:
        return calculate_5d_revenue_gate(
            business_impact=self.business_impact,
            revenue_impact=self.revenue_impact,
            urgency=self.urgency,
            probability_of_success=self.probability_of_success,
            category=self.category,
            estimated_complexity=self.estimated_complexity,
            risk_level=self.risk_level,
            breakdown_override=self.revenue_gate_override,
        )

    @property
    def revenue_gate_score(self) -> float:
        return self.revenue_gate.total_score

    @property
    def is_revenue_gate_passed(self) -> bool:
        return self.revenue_gate.passed

    @property
    def priority_score(self) -> float:
        """Calculate weighted revenue-first priority score."""
        return round(
            self.business_impact * self.revenue_impact * self.probability_of_success * self.urgency,
            2
        )

    def to_dict(self) -> Dict[str, Any]:
        d = self.model_dump()
        d["priority_score"] = self.priority_score
        d["revenue_gate_score"] = self.revenue_gate_score
        d["revenue_gate_verdict"] = self.revenue_gate.verdict
        d["revenue_gate_passed"] = self.is_revenue_gate_passed
        d["revenue_gate_breakdown"] = self.revenue_gate.model_dump()
        return d


class MissionRouter:
    """Ranks and routes engineering missions across the MBM swarm with authoritative 5D Revenue Gating."""

    @classmethod
    def evaluate_revenue_gate(cls, mission_or_dict: Any) -> RevenueGateBreakdown:
        if isinstance(mission_or_dict, EngineeringMission):
            return mission_or_dict.revenue_gate
        elif isinstance(mission_or_dict, dict):
            if "revenue_gate_breakdown" in mission_or_dict and isinstance(mission_or_dict["revenue_gate_breakdown"], dict):
                return RevenueGateBreakdown(**mission_or_dict["revenue_gate_breakdown"])

            b_imp = float(mission_or_dict.get("business_impact", 5.0))
            r_imp = float(mission_or_dict.get("revenue_impact", 5.0))
            urg = float(mission_or_dict.get("urgency", 3.0))
            prob = float(mission_or_dict.get("probability_of_success", 0.9))
            cat = str(mission_or_dict.get("category", "DEVELOPER_PRODUCTIVITY"))
            comp = str(mission_or_dict.get("estimated_complexity", "MEDIUM"))
            risk = str(mission_or_dict.get("risk_level", "LOW"))
            return calculate_5d_revenue_gate(
                business_impact=b_imp,
                revenue_impact=r_imp,
                urgency=urg,
                probability_of_success=prob,
                category=cat,
                estimated_complexity=comp,
                risk_level=risk,
            )
        raise TypeError(f"Expected EngineeringMission or dict, got {type(mission_or_dict)}")

    @classmethod
    def is_revenue_gate_passed(cls, mission_or_dict: Any) -> bool:
        eval_result = cls.evaluate_revenue_gate(mission_or_dict)
        return eval_result.passed

    @classmethod
    def rank_missions(cls, missions: List[EngineeringMission], filter_unapproved: bool = False) -> List[EngineeringMission]:
        # Sort order: 1) revenue gate passed, 2) priority_score, 3) revenue_gate_score
        sorted_missions = sorted(
            missions,
            key=lambda m: (m.is_revenue_gate_passed, m.priority_score, m.revenue_gate_score),
            reverse=True,
        )
        if filter_unapproved:
            return [m for m in sorted_missions if m.is_revenue_gate_passed]
        return sorted_missions

    @classmethod
    def get_routable_missions(cls, missions: List[EngineeringMission]) -> List[EngineeringMission]:
        """Returns only missions meeting the authoritative 5D Revenue Gate (score >= 70.0)."""
        return cls.rank_missions(missions, filter_unapproved=True)


if __name__ == "__main__":
    m = EngineeringMission(
        mission_id="GLM-001",
        title="Enforce Single-Writer Lock on Dialer leads_database.json",
        target_repo="MBM / mbm-dialer",
        target_paths=["mbm-dialer/app/public/leads_database.json", "MBM/GLM/single_writer_lock.py"],
        category="DATA_INTEGRITY",
        assigned_role=GLMRole.RELIABILITY_ENGINEER,
        routing_tier=ModelRoutingTier.DEEP_GLM,
        business_impact=10.0,
        revenue_impact=10.0,
        probability_of_success=0.95,
        urgency=5.0,
        problem_statement="Prevent dataset shrinkage (762 -> 702) by routing all DB writes through DialerSingleWriter gateway.",
        recommended_fix="Integrate single_writer_lock.py into all lead factory and recovery scripts.",
    )
    print(f"Mission: {m.title}")
    print(f"Priority Score: {m.priority_score}")
    print(f"Revenue Gate Score: {m.revenue_gate_score}/100 ({m.revenue_gate.verdict})")
    print(f"Breakdown: {m.revenue_gate.model_dump()}")
