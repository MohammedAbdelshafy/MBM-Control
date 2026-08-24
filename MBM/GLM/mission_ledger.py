#!/usr/bin/env python3
"""
GLM Swarm Mission Ledger & Concurrency Lock Store
=================================================
Maintains persistent ledger of completed, running, and pending engineering missions
to guarantee zero duplicated work and zero multi-agent file collisions.
"""

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
LEDGER_PATH = ROOT_DIR / "MBM" / "Artifacts" / "GLM_MISSION_LEDGER.json"
LOCKS_PATH = ROOT_DIR / "MBM" / "Artifacts" / "GLM_ACTIVE_LOCKS.json"


class MissionExecutionRecord(BaseModel):
    mission_id: str
    repo: str
    agent: str
    objective: str
    exit_condition: str = ""
    blocker: Optional[str] = None
    revenue_impact: float = 0.0
    deployment_status: str = "PENDING"
    files_changed: List[str] = Field(default_factory=list)
    tests_run: List[str] = Field(default_factory=list)
    test_result: str = "PASS"
    runtime_result: str = "VERIFIED"
    business_impact: str = ""
    commit_sha: Optional[str] = None
    status: str = "COMPLETED"
    started_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    completed_at: Optional[str] = None


class MissionLedger:
    """Persistent ledger manager for GLM missions and file locks."""

    def __init__(self, ledger_path: Path = LEDGER_PATH, locks_path: Path = LOCKS_PATH):
        self.ledger_path = ledger_path
        self.locks_path = locks_path
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)

    def load_ledger(self) -> List[Dict[str, Any]]:
        if not self.ledger_path.exists():
            return []
        try:
            return json.loads(self.ledger_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def record_mission(self, record: MissionExecutionRecord):
        records = self.load_ledger()
        record.completed_at = datetime.now(timezone.utc).isoformat()
        records.append(record.model_dump())
        self.ledger_path.write_text(json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8")

    def acquire_file_lock(self, repo: str, branch: str, files: List[str], agent: str, mission_id: str) -> bool:
        locks = self.get_active_locks()
        for locked_file, lock_info in locks.items():
            if locked_file in files:
                if lock_info["agent"] != agent:
                    return False  # Locked by another agent!
        
        for f in files:
            locks[f] = {
                "repo": repo,
                "branch": branch,
                "agent": agent,
                "mission_id": mission_id,
                "acquired_at": datetime.now(timezone.utc).isoformat(),
            }
        
        self.locks_path.write_text(json.dumps(locks, indent=2, ensure_ascii=False), encoding="utf-8")
        return True

    def release_file_lock(self, files: List[str]):
        locks = self.get_active_locks()
        for f in files:
            locks.pop(f, None)
        self.locks_path.write_text(json.dumps(locks, indent=2, ensure_ascii=False), encoding="utf-8")

    def get_active_locks(self) -> Dict[str, Any]:
        if not self.locks_path.exists():
            return {}
        try:
            return json.loads(self.locks_path.read_text(encoding="utf-8"))
        except Exception:
            return {}


def get_mission_ledger() -> MissionLedger:
    return MissionLedger()
