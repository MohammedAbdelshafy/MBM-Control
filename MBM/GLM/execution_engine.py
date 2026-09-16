#!/usr/bin/env python3
"""
GLM Swarm Execution Engine
==========================
Transforms GLM from a read-only analyzer into a production-connected force.
Reads priority queues, assigns missions, executes them with measurable
exit conditions, and updates the ledger.
"""

import sys
import json
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.GLM.mission_ledger import get_mission_ledger, MissionExecutionRecord
from MBM.GLM.orchestrator import get_orchestrator
from MBM.GLM.scoreboard_updater import update_scoreboard
from MBM.GLM.mission_router import MissionRouter, REVENUE_GATE_THRESHOLD

TOP25_JSON_PATH = ROOT_DIR / "MBM" / "Artifacts" / "GLM_TOP25_MISSIONS.json"


class ExecutionEngine:
    def __init__(self):
        self.orchestrator = get_orchestrator()
        self.ledger = get_mission_ledger()

    def load_priority_queue(self):
        if not TOP25_JSON_PATH.exists():
            print("Running orchestrator audit to generate priority queue...")
            self.orchestrator.run_read_only_audit()
        return json.loads(TOP25_JSON_PATH.read_text(encoding="utf-8"))

    def execute_next_mission(self):
        queue = self.load_priority_queue()
        ledger_records = self.ledger.load_ledger()
        completed_ids = {
            r.get("mission_id")
            for r in ledger_records
            if r.get("status") in ["COMPLETED", "PRODUCTIVE"]
        }

        target_mission = None
        for mission in queue:
            m_id = mission["mission_id"]
            if m_id not in completed_ids and mission["urgency"] >= 4.0:
                target_mission = mission
                break

        if not target_mission:
            for mission in queue:
                if mission["mission_id"] not in completed_ids:
                    target_mission = mission
                    break

        if not target_mission:
            print("No pending missions in the queue.")
            return None

        # Authoritative 5D Revenue Gate enforcement (score >= 70.0)
        revenue_eval = MissionRouter.evaluate_revenue_gate(target_mission)
        if not revenue_eval.passed:
            blocker = (
                f"Mission {target_mission['mission_id']} failed 5D Revenue Gate "
                f"(score: {revenue_eval.total_score:.1f} < {REVENUE_GATE_THRESHOLD}). "
                f"Verdict: {revenue_eval.verdict}. Cannot be routed for execution."
            )
            print(f"Mission {target_mission['mission_id']} REJECTED. {blocker}")
            self._record_failure(target_mission, "REJECTED", blocker)
            return None

        print(f"Assigning Mission: {target_mission['mission_id']} - {target_mission['title']}")
        print(f"Role: {target_mission['assigned_role']} | Target: {target_mission['target_repo']}")

        lock_acquired = self.ledger.acquire_file_lock(
            repo=target_mission["target_repo"],
            branch="main",
            files=target_mission["target_paths"],
            agent=target_mission["assigned_role"],
            mission_id=target_mission["mission_id"]
        )

        if not lock_acquired:
            print(f"Mission {target_mission['mission_id']} BLOCKED. Files locked by another agent.")
            self._record_failure(target_mission, "BLOCKED", "Files currently locked by another process.")
            return None

        blocker = "No concrete execution adapter is registered for this mission."
        print(f"Mission {target_mission['mission_id']} BLOCKED. {blocker}")
        try:
            self._record_failure(target_mission, "BLOCKED", blocker)
        finally:
            self.ledger.release_file_lock(target_mission["target_paths"])
        return None

    def _record_failure(self, mission: dict, status: str, blocker: str):
        record = MissionExecutionRecord(
            mission_id=mission["mission_id"],
            repo=mission["target_repo"],
            agent=mission["assigned_role"],
            objective=mission["recommended_fix"],
            exit_condition="",
            blocker=blocker,
            revenue_impact=0.0,
            deployment_status="NOT_DEPLOYED",
            files_changed=[],
            tests_run=[],
            test_result="NOT_RUN",
            runtime_result="NOT_RUN",
            business_impact=str(mission.get("business_impact", "")),
            status=status,
        )
        self.ledger.record_mission(record)
        update_scoreboard()


if __name__ == "__main__":
    engine = ExecutionEngine()
    engine.execute_next_mission()
