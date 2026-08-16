#!/usr/bin/env python3
"""
GLM Swarm Mission Router & Priority Engine
==========================================
Calculates priority scores using the canonical business formula:
  Priority = Business Impact (1-10) * Revenue Impact (1-10) * Probability of Success (0.1-1.0) * Urgency (1-5)
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime, timezone
from MBM.GLM.agent_registry import GLMRole, ModelRoutingTier


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
        return d


class MissionRouter:
    """Ranks and routes engineering missions across the MBM swarm."""

    @staticmethod
    def rank_missions(missions: List[EngineeringMission]) -> List[EngineeringMission]:
        return sorted(missions, key=lambda m: m.priority_score, reverse=True)


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
