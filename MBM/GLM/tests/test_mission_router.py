import pytest
from pathlib import Path
from MBM.GLM.mission_router import (
    EngineeringMission,
    MissionRouter,
    MissionCategory,
    RevenueGateBreakdown,
    REVENUE_GATE_THRESHOLD,
    calculate_5d_revenue_gate,
)
from MBM.GLM.agent_registry import GLMRole, ModelRoutingTier
from MBM.GLM.execution_engine import ExecutionEngine
from MBM.GLM.mission_ledger import MissionExecutionRecord


class FakeLedger:
    def __init__(self, records=None):
        self.records = list(records or [])
        self.locks = {}

    def load_ledger(self):
        return list(self.records)

    def get_active_locks(self):
        return dict(self.locks)

    def acquire_file_lock(self, **kwargs):
        for path in kwargs["files"]:
            self.locks[path] = kwargs
        return True

    def release_file_lock(self, files):
        for path in files:
            self.locks.pop(path, None)

    def record_mission(self, record):
        self.records.append(record.model_dump())


class FakeOrchestrator:
    def run_read_only_audit(self):
        raise AssertionError("queue should be supplied by the test")


def make_engine(queue):
    engine = ExecutionEngine.__new__(ExecutionEngine)
    engine.orchestrator = FakeOrchestrator()
    engine.ledger = FakeLedger()
    engine._test_queue = queue
    return engine


def test_missions_below_revenue_gate_cannot_be_routed_for_execution(monkeypatch):
    """Proves that a mission scoring < 70.0 is rejected before lock acquisition or execution."""
    sub_threshold_mission = {
        "mission_id": "GLM-LOW-001",
        "title": "Low Value Speculative Task",
        "target_repo": "MBM-Control",
        "target_paths": ["README.md"],
        "assigned_role": "GLM_TEST_ENGINEER",
        "recommended_fix": "Minor format change",
        "urgency": 1.0,
        "business_impact": 2.0,
        "revenue_impact": 1.0,
        "probability_of_success": 0.5,
        "category": "DOCUMENTATION",
        "estimated_complexity": "HIGH",
        "risk_level": "HIGH",
    }
    engine = make_engine([sub_threshold_mission])
    monkeypatch.setattr(engine, "load_priority_queue", lambda: [sub_threshold_mission])
    monkeypatch.setattr("MBM.GLM.execution_engine.update_scoreboard", lambda: None)

    result = engine.execute_next_mission()

    # Must return None (unexecuted)
    assert result is None

    # Must have recorded failure in ledger as REJECTED
    assert len(engine.ledger.records) == 1
    record = engine.ledger.records[0]
    assert record["status"] == "REJECTED"
    assert record["revenue_impact"] == 0.0
    assert record["deployment_status"] == "NOT_DEPLOYED"
    assert record["test_result"] == "NOT_RUN"
    assert record["runtime_result"] == "NOT_RUN"
    assert "failed 5D Revenue Gate" in record["blocker"]

    # Locks must NEVER have been acquired
    assert len(engine.ledger.locks) == 0


def test_missions_meeting_gate_can_proceed_to_adapter_stage(monkeypatch):
    """Proves that a mission meeting >= 70.0 passes the gate and proceeds to adapter verification."""
    approved_mission = {
        "mission_id": "GLM-HIGH-001",
        "title": "P4 DFY Lead Cleaner Fulfillment Core",
        "target_repo": "MBM-Control",
        "target_paths": ["productized-service/p4-lead-cleaner/clean_leads.py"],
        "assigned_role": "GLM_GTM_ENGINEER",
        "recommended_fix": "Package DFY lead cleaning pipeline",
        "urgency": 5.0,
        "business_impact": 10.0,
        "revenue_impact": 10.0,
        "probability_of_success": 0.98,
        "category": "GTM_REVENUE",
        "estimated_complexity": "LOW",
        "risk_level": "LOW",
    }
    engine = make_engine([approved_mission])
    monkeypatch.setattr(engine, "load_priority_queue", lambda: [approved_mission])
    monkeypatch.setattr("MBM.GLM.execution_engine.update_scoreboard", lambda: None)

    result = engine.execute_next_mission()

    assert result is None
    assert len(engine.ledger.records) == 1
    record = engine.ledger.records[0]

    # It cleared the revenue gate! But fails closed on adapter check (Objective 004)
    assert record["status"] == "BLOCKED"
    assert "No concrete execution adapter is registered" in record["blocker"]
    assert record["revenue_impact"] == 0.0
    assert record["deployment_status"] == "NOT_DEPLOYED"


def test_routing_cannot_manufacture_revenue_evidence():
    """Proves that routing and gating cannot create non-zero revenue evidence."""
    m = EngineeringMission(
        mission_id="GLM-999",
        title="High Value Revenue Asset",
        target_repo="MBM",
        target_paths=["MBM/LeadEngine"],
        category=MissionCategory.REVENUE_BLOCKER,
        assigned_role=GLMRole.MONETIZATION_ENGINEER,
        routing_tier=ModelRoutingTier.DEEP_GLM,
        business_impact=10.0,
        revenue_impact=10.0,
        probability_of_success=1.0,
        urgency=5.0,
        problem_statement="Test revenue separation",
        recommended_fix="Verify zero fake revenue",
    )
    # Gating evaluates potential, but does NOT assert realized revenue
    assert m.revenue_gate_score >= REVENUE_GATE_THRESHOLD
    assert m.is_revenue_gate_passed is True

    record = MissionExecutionRecord(
        mission_id=m.mission_id,
        repo=m.target_repo,
        agent=m.assigned_role,
        objective=m.recommended_fix,
        blocker="Awaiting execution adapter",
        revenue_impact=0.0,
        deployment_status="NOT_DEPLOYED",
    )
    assert record.revenue_impact == 0.0
    assert record.test_result == "NOT_RUN"
    assert record.runtime_result == "NOT_RUN"
    assert record.status == "PLANNED"


def test_blocked_missions_remain_blocked(monkeypatch):
    """Proves that blocked missions are not re-routed or treated as completed."""
    mission = {
        "mission_id": "GLM-BLOCKED-001",
        "title": "Already Blocked Task",
        "target_repo": "MBM",
        "target_paths": ["README.md"],
        "assigned_role": "GLM_TEST_ENGINEER",
        "recommended_fix": "Fix something",
        "urgency": 5.0,
        "business_impact": 10.0,
        "revenue_impact": 10.0,
        "probability_of_success": 0.95,
        "category": "DATA_INTEGRITY",
    }
    # Pre-populate ledger with BLOCKED status
    existing_record = {
        "mission_id": "GLM-BLOCKED-001",
        "status": "BLOCKED",
        "revenue_impact": 0.0,
    }
    engine = make_engine([mission])
    engine.ledger.records.append(existing_record)
    monkeypatch.setattr(engine, "load_priority_queue", lambda: [mission])
    monkeypatch.setattr("MBM.GLM.execution_engine.update_scoreboard", lambda: None)

    result = engine.execute_next_mission()
    assert result is None
    latest_record = engine.ledger.records[-1]
    assert latest_record["status"] == "BLOCKED"
    assert latest_record["revenue_impact"] == 0.0


def test_execution_truth_remains_independent_from_routing_approval():
    """Proves that routing approval does not imply or synthesize execution truth."""
    breakdown = calculate_5d_revenue_gate(
        business_impact=10.0,
        revenue_impact=10.0,
        urgency=5.0,
        probability_of_success=1.0,
        category="GTM_REVENUE",
        estimated_complexity="LOW",
        risk_level="LOW",
    )
    assert breakdown.total_score == 100.0
    assert breakdown.passed is True
    assert breakdown.verdict == "APPROVED"

    rec = MissionExecutionRecord(
        mission_id="GLM-PERFECT-001",
        repo="MBM",
        agent="GLM_GTM_ENGINEER",
        objective="Ship DFY Lead Cleaner",
        exit_condition="",
        blocker="Execution pending human approval",
        revenue_impact=0.0,
        deployment_status="NOT_DEPLOYED",
        status="PLANNED",
    )
    assert rec.status == "PLANNED"
    assert rec.test_result == "NOT_RUN"
    assert rec.runtime_result == "NOT_RUN"
    assert rec.revenue_impact == 0.0


def test_get_routable_missions_filters_sub_threshold():
    """Proves that get_routable_missions() only returns missions meeting >= 70.0."""
    high_m = EngineeringMission(
        mission_id="GLM-HI",
        title="High value",
        target_repo="MBM",
        target_paths=["a.py"],
        category=MissionCategory.REVENUE_BLOCKER,
        assigned_role=GLMRole.MONETIZATION_ENGINEER,
        routing_tier=ModelRoutingTier.DEEP_GLM,
        business_impact=10.0,
        revenue_impact=10.0,
        probability_of_success=0.95,
        urgency=5.0,
        problem_statement="Prob",
        recommended_fix="Fix",
    )
    low_m = EngineeringMission(
        mission_id="GLM-LO",
        title="Low value",
        target_repo="MBM",
        target_paths=["b.py"],
        category=MissionCategory.DOCUMENTATION,
        assigned_role=GLMRole.DOCUMENTATION_ENGINEER,
        routing_tier=ModelRoutingTier.LIGHT,
        business_impact=1.0,
        revenue_impact=1.0,
        probability_of_success=0.3,
        urgency=1.0,
        problem_statement="Prob",
        recommended_fix="Fix",
    )
    assert high_m.is_revenue_gate_passed is True
    assert low_m.is_revenue_gate_passed is False

    routable = MissionRouter.get_routable_missions([low_m, high_m])
    assert len(routable) == 1
    assert routable[0].mission_id == "GLM-HI"


def test_5d_rubric_dimension_boundaries():
    """Proves 5D rubric enforces maximum scores per dimension from AGENTIC_5D_REVENUE_GATE.md."""
    breakdown = calculate_5d_revenue_gate(
        business_impact=10.0,
        revenue_impact=10.0,
        urgency=5.0,
        probability_of_success=1.0,
        category="REVENUE_BLOCKER",
        estimated_complexity="LOW",
        risk_level="LOW",
    )
    assert breakdown.business_value == 20.0       # Max 20
    assert breakdown.revenue_potential == 20.0     # Max 20
    assert breakdown.customer_urgency == 15.0      # Max 15
    assert breakdown.implementation_fit == 15.0    # Max 15
    assert breakdown.reusability == 10.0           # Max 10
    assert breakdown.time_to_value == 10.0         # Max 10
    assert breakdown.risk_reduction == 10.0        # Max 10
    assert breakdown.total_score == 100.0          # Max 100
