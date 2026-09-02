"""
GenerationJob — trackable job for every external generation call (§16).

Statuses: QUEUED | RUNNING | SUCCEEDED | FAILED | BLOCKED | RETRYING | CANCELLED
Retries are bounded; non-retryable errors fail closed.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

STATUSES = ("QUEUED", "RUNNING", "SUCCEEDED", "FAILED", "BLOCKED", "RETRYING", "CANCELLED")
RETRYABLE = {"TIMEOUT", "RATE_LIMITED", "TRANSIENT", "NETWORK"}
NON_RETRYABLE = {"AUTH_FAILED", "BLOCKED", "INVALID_INPUT", "QUOTA_EXHAUSTED", "VALIDATION_FAILED"}

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def input_hash(payload: Dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]

@dataclass
class GenerationJob:
    id: str
    provider: str
    inputHash: str
    status: str = "QUEUED"
    providerJobId: Optional[str] = None
    attempts: int = 0
    maxAttempts: int = 3
    createdAt: str = field(default_factory=_now)
    startedAt: Optional[str] = None
    finishedAt: Optional[str] = None
    errorCode: Optional[str] = None
    errorMessage: Optional[str] = None
    idempotencyKey: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    result: Dict[str, Any] = field(default_factory=dict)

    def can_retry(self) -> bool:
        if self.attempts >= self.maxAttempts:
            return False
        if self.errorCode in NON_RETRYABLE:
            return False
        return True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class JobStore:
    """File-backed job store (additive, isolated from lead DB)."""
    def __init__(self, path: Optional[Path] = None):
        # Stored under MBM/Artifacts/intelligence/ — gitignored for PII safety.
        from pathlib import Path as _P
        default = _P(__file__).resolve().parents[3] / "MBM" / "Artifacts" / "intelligence" / "generation_jobs.json"
        self.path = Path(path) if path else default
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def _read(self) -> List[Dict[str, Any]]:
        try:
            if self.path.exists():
                data = json.loads(self.path.read_text(encoding="utf-8"))
                if isinstance(data, list):
                    return data
        except Exception:
            pass
        return []

    def _write(self, items: List[Dict[str, Any]]) -> None:
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(items, indent=2, default=str), encoding="utf-8")
        tmp.replace(self.path)

    def upsert(self, job: GenerationJob) -> None:
        items = self._read()
        for i, it in enumerate(items):
            if it.get("id") == job.id:
                items[i] = job.to_dict()
                self._write(items)
                return
        items.append(job.to_dict())
        self._write(items)

    def get(self, job_id: str) -> Optional[Dict[str, Any]]:
        for it in self._read():
            if it.get("id") == job_id:
                return it
        return None

    def list(self, provider: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        items = self._read()
        if provider:
            items = [x for x in items if x.get("provider") == provider]
        if status:
            items = [x for x in items if x.get("status") == status]
        return items
