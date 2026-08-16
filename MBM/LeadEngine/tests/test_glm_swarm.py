import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import pytest
from MBM.GLM.agent_registry import GLMRole, ModelRoutingTier, get_agent, AGENT_REGISTRY
from MBM.GLM.mission_router import EngineeringMission, MissionRouter, MissionCategory
from MBM.GLM.mission_ledger import MissionLedger, MissionExecutionRecord
from MBM.GLM.single_writer_lock import DialerSingleWriter, SingleWriterViolation
from MBM.GLM.core_agents import ReviewAgent, SecurityAgent, PerformanceAgent, ReliabilityAgent
from MBM.GLM.revenue_and_gtm_agents import MonetizationEngineerAgent, DialerEngineerAgent
from MBM.GLM.orchestrator import GLMOrchestrator, get_orchestrator


def test_agent_registry_16_roles():
    assert len(AGENT_REGISTRY) >= 16
    assert GLMRole.ARCHITECT in AGENT_REGISTRY
    assert GLMRole.RELIABILITY_ENGINEER in AGENT_REGISTRY
    assert GLMRole.DIALER_ENGINEER in AGENT_REGISTRY
    assert GLMRole.GTM_ENGINEER in AGENT_REGISTRY
    assert GLMRole.REVENUE_ANALYST in AGENT_REGISTRY

    arch = get_agent(GLMRole.ARCHITECT)
    assert arch.preferred_tier == ModelRoutingTier.DEEP_GLM
    assert "dependency_mapping" in arch.capabilities


def test_mission_priority_formula():
    m = EngineeringMission(
        mission_id="TEST-001",
        title="Test Mission",
        target_repo="MBM",
        target_paths=["test.py"],
        category=MissionCategory.DATA_INTEGRITY,
        assigned_role=GLMRole.RELIABILITY_ENGINEER,
        routing_tier=ModelRoutingTier.DEEP_GLM,
        business_impact=10.0,
        revenue_impact=10.0,
        probability_of_success=0.9,
        urgency=5.0,
        problem_statement="Test problem",
        recommended_fix="Test fix",
    )
    # 10 * 10 * 0.9 * 5 = 450.0
    assert m.priority_score == 450.0


def test_mission_router_ranking():
    m1 = EngineeringMission(
        mission_id="M1",
        title="Low Priority",
        target_repo="MBM",
        target_paths=[],
        category=MissionCategory.DOCUMENTATION,
        assigned_role=GLMRole.DOCUMENTATION_ENGINEER,
        routing_tier=ModelRoutingTier.LIGHT,
        business_impact=5.0,
        revenue_impact=5.0,
        probability_of_success=0.8,
        urgency=2.0,
        problem_statement="Low",
        recommended_fix="Low",
    )
    m2 = EngineeringMission(
        mission_id="M2",
        title="High Priority",
        target_repo="MBM",
        target_paths=[],
        category=MissionCategory.CRITICAL_PRODUCTION_BUG,
        assigned_role=GLMRole.RELIABILITY_ENGINEER,
        routing_tier=ModelRoutingTier.DEEP_GLM,
        business_impact=10.0,
        revenue_impact=10.0,
        probability_of_success=0.95,
        urgency=5.0,
        problem_statement="Critical",
        recommended_fix="Critical",
    )
    ranked = MissionRouter.rank_missions([m1, m2])
    assert ranked[0].mission_id == "M2"
    assert ranked[1].mission_id == "M1"


def test_single_writer_lock_protects_shrinkage(tmp_path):
    db_file = tmp_path / "leads_database.json"
    initial_leads = [{"id": "L1", "phone": "2142340101"}, {"id": "L2", "phone": "2142340102"}]
    import json
    db_file.write_text(json.dumps(initial_leads), encoding="utf-8")

    writer = DialerSingleWriter(db_path=db_file)
    writer.lock_file = tmp_path / ".lock"
    writer.backup_dir = tmp_path / "backups"
    writer.backup_dir.mkdir(parents=True, exist_ok=True)

    # Valid non-destructive upsert
    res = writer.commit_update([{"id": "L3", "phone": "2142340103"}], author="TEST")
    assert res["ok"] is True
    assert res["final_count"] == 3

    # Attempt to read
    leads = writer.read_leads()
    assert len(leads) == 3


def test_mission_ledger_locking(tmp_path):
    ledger = MissionLedger(ledger_path=tmp_path / "ledger.json", locks_path=tmp_path / "locks.json")
    
    # Agent 1 acquires lock
    ok1 = ledger.acquire_file_lock(
        repo="mbm-dialer",
        branch="master",
        files=["leads_database.json"],
        agent="GLM_DIALER",
        mission_id="GLM-001",
    )
    assert ok1 is True

    # Agent 2 tries to acquire same file -> blocked
    ok2 = ledger.acquire_file_lock(
        repo="mbm-dialer",
        branch="master",
        files=["leads_database.json"],
        agent="GLM_REVENUE",
        mission_id="GLM-002",
    )
    assert ok2 is False

    # Release lock
    ledger.release_file_lock(["leads_database.json"])

    # Agent 2 tries again -> success
    ok3 = ledger.acquire_file_lock(
        repo="mbm-dialer",
        branch="master",
        files=["leads_database.json"],
        agent="GLM_REVENUE",
        mission_id="GLM-002",
    )
    assert ok3 is True


def test_orchestrator_read_only_audit():
    orch = get_orchestrator()
    audit_res = orch.run_read_only_audit()
    assert audit_res["status"] == "READ_ONLY_AUDIT_COMPLETED"
    assert audit_res["ranked_missions_count"] == 25
    assert audit_res["top_mission"]["mission_id"] == "GLM-001"
    assert audit_res["report"]["summary"]["repos_improved"] >= 7
