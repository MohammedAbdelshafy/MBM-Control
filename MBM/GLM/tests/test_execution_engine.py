import json
from pathlib import Path

from MBM.GLM.execution_engine import ExecutionEngine


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


def test_execute_next_mission_does_not_claim_success_without_adapter(monkeypatch):
    queue = [
        {
            "mission_id": "GLM-TEST-001",
            "title": "Test mission",
            "target_repo": "MBM-Control",
            "target_paths": ["README.md"],
            "assigned_role": "GLM_TEST_ENGINEER",
            "recommended_fix": "Do a real thing",
            "urgency": 5.0,
            "business_impact": 9.0,
        }
    ]
    engine = make_engine(queue)
    monkeypatch.setattr(engine, "load_priority_queue", lambda: queue)
    monkeypatch.setattr("MBM.GLM.execution_engine.update_scoreboard", lambda: None)

    result = engine.execute_next_mission()

    assert result is None
    assert len(engine.ledger.records) == 1
    record = engine.ledger.records[0]
    assert record["status"] == "BLOCKED"
    assert record["revenue_impact"] == 0.0
    assert record["deployment_status"] == "NOT_DEPLOYED"
    assert record["files_changed"] == []
    assert record["tests_run"] == []
    assert record["test_result"] == "NOT_RUN"
    assert record["runtime_result"] == "NOT_RUN"


def test_execution_engine_has_no_simulated_success_code():
    source = Path(__file__).resolve().parents[1].joinpath("execution_engine.py").read_text(encoding="utf-8")
    assert "time.sleep(2)" not in source
    assert "revenue_impact"] * 1000" not in source
    assert 'status="PRODUCTIVE"' not in source
    assert 'deployment_status="DEPLOYED"' not in source
