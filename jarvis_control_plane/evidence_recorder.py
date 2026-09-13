"""Evidence Recorder for Ecosystem Provider execution.

Produces verifiable records of all external provider executions.
"""

from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_DIR = ROOT / "MBM" / "Artifacts" / "evidence"

class EvidenceStatus:
    VERIFIED = "VERIFIED"
    UNVERIFIED = "UNVERIFIED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"


def record_execution(
    mission_id: str,
    provider_id: str,
    commit_sha: str,
    capability: str,
    permission: str,
    executor: str,
    status: str,
    start_time: datetime,
    end_time: datetime,
    artifacts: List[str] = None,
    files_changed: List[str] = None,
    network_scope: str = "none",
    fallback_used: bool = False,
    verification_result: str = "",
    approval_id: Optional[str] = None
) -> str:
    """Record a piece of execution evidence to a JSON ledger."""
    
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    
    evidence = {
        "mission_id": mission_id,
        "provider": provider_id,
        "commit_sha": commit_sha,
        "capability": capability,
        "permission": permission,
        "approval_id": approval_id,
        "executor": executor,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "status": status,
        "artifacts": artifacts or [],
        "files_changed": files_changed or [],
        "network_scope": network_scope,
        "fallback_used": fallback_used,
        "verification_result": verification_result,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    filename = EVIDENCE_DIR / f"evidence_{mission_id}_{int(datetime.now(timezone.utc).timestamp())}.json"
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(evidence, f, indent=2)
        
    return str(filename)
