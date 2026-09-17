"""State / memory separation (P0.8).

Six isolated scopes — never one giant memory store:

    WORKING      — scratch for the current task (discardable)
    SESSION      — conversation/session context (per run_id)
    OPERATIONAL  — workflow runs, policies, audit, replay (control plane owned)
    CANONICAL    — business truth: leads, dialer state, suppression (EXISTING
                   systems own this; this module only adapts to them)
    MEMORY       — long-term distilled learnings (explicit writes only)
    RAG          — knowledge retrieval index (read-only at runtime)

Canonical writes go exclusively through :class:`CanonicalLeadStore`, a thin
adapter over the existing MBM.GLM.single_writer_lock.DialerSingleWriter
(zero dataset shrinkage, atomic backup, audit sidecar). No second lead
database is created here.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


class StateScope(str, Enum):
    WORKING = "working"
    SESSION = "session"
    OPERATIONAL = "operational"
    CANONICAL = "canonical"
    MEMORY = "memory"
    RAG = "rag"


class ScopeViolationError(ValueError):
    pass


class IsolatedStateStore:
    """In-memory namespaced store with hard scope isolation.

    Reads/writes declare their scope. Cross-scope access must go through an
    explicit adapter (e.g. CanonicalLeadStore) so leaks are visible in review.
    """

    _READ_ONLY_SCOPES = frozenset({StateScope.RAG})

    def __init__(self) -> None:
        self._data: Dict[StateScope, Dict[str, Any]] = {s: {} for s in StateScope}

    def write(self, scope: StateScope, key: str, value: Any) -> None:
        if scope in self._READ_ONLY_SCOPES:
            raise ScopeViolationError(f"scope {scope.value} is read-only at runtime")
        if scope is StateScope.CANONICAL:
            raise ScopeViolationError(
                "canonical writes must go through CanonicalLeadStore (single-writer), not the generic store"
            )
        self._data[scope][key] = value

    def read(self, scope: StateScope, key: str, default: Any = None) -> Any:
        return self._data[scope].get(key, default)

    def keys(self, scope: StateScope) -> List[str]:
        return list(self._data[scope].keys())

    def promote_to_memory(self, key: str, value: Any, source_scope: StateScope) -> None:
        """Explicit, auditable promotion into long-term memory only."""
        if source_scope is StateScope.CANONICAL:
            raise ScopeViolationError("canonical records are never copied into memory; store references only")
        self._data[StateScope.MEMORY][key] = {"value": value, "source_scope": source_scope.value}


class CanonicalLeadStore:
    """Adapter: the ONLY control-plane path to canonical lead state.

    Delegates every mutation to the existing DialerSingleWriter so all
    production invariants (mutex, monotonic non-shrink, backup, audit,
    verification gate) are preserved untouched.
    """

    def __init__(self, db_path: Optional[Path] = None):
        from MBM.GLM.single_writer_lock import DialerSingleWriter

        kwargs: Dict[str, Any] = {}
        if db_path is not None:
            kwargs["db_path"] = Path(db_path)
        self._writer = DialerSingleWriter(**kwargs)

    @property
    def db_path(self) -> Path:
        return self._writer.db_path

    def read_all(self) -> List[Dict[str, Any]]:
        """Canonical read through the existing single-writer (identical semantics)."""
        return self._writer.read_leads()

    def verified_for_dialer(self) -> List[Dict[str, Any]]:
        """Canonical read through the existing verification gate (no bypass)."""
        from MBM.LeadEngine.dialer_verification_gate import filter_for_dialer

        return filter_for_dialer(self.read_all(), quiet=True)

    def update(self, *args: Any, **kwargs: Any) -> Any:
        """Forward to DialerSingleWriter.commit_update — identical contract, no new semantics."""
        commit = getattr(self._writer, "commit_update", None)
        if commit is None:
            raise AttributeError("underlying DialerSingleWriter exposes no commit_update(); refusing second implementation")
        return commit(*args, **kwargs)
