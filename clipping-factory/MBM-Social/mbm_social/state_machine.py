"""
Production State Machine — enforces valid lifecycle transitions.

Valid states:
  DISCOVERED → PROCESSING → CLIPPED → RENDERED → QA_APPROVED
  → READY_TO_PUBLISH → PUBLISH_REQUESTED → PUBLISHED → VERIFIED

Failure states:
  QA_REJECTED, PUBLISH_BLOCKED, PUBLISH_FAILED, VERIFY_FAILED, RETRY_PENDING
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


VALID_STATES = {
    "DISCOVERED", "PROCESSING", "CLIPPED", "RENDERED",
    "QA_APPROVED", "READY_TO_PUBLISH", "PUBLISH_REQUESTED",
    "PUBLISHED", "VERIFIED",
}

FAILURE_STATES = {
    "QA_REJECTED", "PUBLISH_BLOCKED", "PUBLISH_FAILED",
    "VERIFY_FAILED", "RETRY_PENDING",
}

ALL_STATES = VALID_STATES | FAILURE_STATES

# Allowed transitions: source -> set of allowed targets
TRANSITIONS = {
    "DISCOVERED": {"PROCESSING", "PUBLISH_BLOCKED"},
    "PROCESSING": {"CLIPPED", "QA_REJECTED", "PUBLISH_BLOCKED"},
    "CLIPPED": {"RENDERED", "QA_REJECTED"},
    "RENDERED": {"QA_APPROVED", "QA_REJECTED"},
    "QA_APPROVED": {"READY_TO_PUBLISH", "PUBLISH_BLOCKED"},
    "READY_TO_PUBLISH": {"PUBLISH_REQUESTED", "PUBLISH_BLOCKED"},
    "PUBLISH_REQUESTED": {"PUBLISHED", "PUBLISH_FAILED", "RETRY_PENDING"},
    "PUBLISHED": {"VERIFIED", "VERIFY_FAILED", "RETRY_PENDING"},
    "VERIFIED": set(),  # Terminal state
    # Failure transitions
    "QA_REJECTED": {"PROCESSING", "DISCOVERED"},
    "PUBLISH_BLOCKED": {"READY_TO_PUBLISH", "DISCOVERED"},
    "PUBLISH_FAILED": {"RETRY_PENDING", "PUBLISH_BLOCKED"},
    "VERIFY_FAILED": {"RETRY_PENDING", "PUBLISH_FAILED"},
    "RETRY_PENDING": {"PUBLISH_REQUESTED", "PUBLISH_FAILED", "VERIFY_FAILED"},
}


@dataclass
class StateTransition:
    from_state: str
    to_state: str
    timestamp: str
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AssetState:
    """State of a single asset in the production pipeline."""
    asset_id: str
    current_state: str = "DISCOVERED"
    history: List[StateTransition] = field(default_factory=list)
    retry_count: int = 0
    max_retries: int = 3
    last_error: str = ""

    def can_transition(self, to_state: str) -> bool:
        """Check if a transition is valid."""
        return to_state in TRANSITIONS.get(self.current_state, set())

    def transition(self, to_state: str, reason: str = "", **metadata) -> bool:
        """Execute a state transition. Returns True if successful."""
        if not self.can_transition(to_state):
            return False

        if to_state in FAILURE_STATES:
            self.retry_count += 1

        transition = StateTransition(
            from_state=self.current_state,
            to_state=to_state,
            timestamp=datetime.now(timezone.utc).isoformat(),
            reason=reason,
            metadata=metadata,
        )

        self.history.append(transition)
        self.current_state = to_state
        return True

    @property
    def is_terminal(self) -> bool:
        return self.current_state == "VERIFIED"

    @property
    def is_failure(self) -> bool:
        return self.current_state in FAILURE_STATES

    @property
    def is_retry_exhausted(self) -> bool:
        return self.retry_count >= self.max_retries

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "current_state": self.current_state,
            "history": [
                {
                    "from": t.from_state,
                    "to": t.to_state,
                    "timestamp": t.timestamp,
                    "reason": t.reason,
                }
                for t in self.history
            ],
            "retry_count": self.retry_count,
            "is_terminal": self.is_terminal,
            "is_failure": self.is_failure,
        }


class ProductionStateMachine:
    """Manages state for all assets in the pipeline."""

    def __init__(self, state_file: Optional[Path] = None):
        self.state_file = state_file
        self.assets: Dict[str, AssetState] = {}
        if state_file and state_file.exists():
            self._load()

    def _load(self):
        """Load state from file."""
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            for asset_id, state_data in data.get("assets", {}).items():
                asset = AssetState(
                    asset_id=asset_id,
                    current_state=state_data.get("current_state", "DISCOVERED"),
                    retry_count=state_data.get("retry_count", 0),
                )
                for h in state_data.get("history", []):
                    asset.history.append(StateTransition(
                        from_state=h["from"],
                        to_state=h["to"],
                        timestamp=h["timestamp"],
                        reason=h.get("reason", ""),
                    ))
                self.assets[asset_id] = asset
        except Exception:
            pass

    def _save(self):
        """Save state to file."""
        if not self.state_file:
            return
        data = {
            "assets": {
                aid: {
                    "current_state": a.current_state,
                    "history": [
                        {"from": t.from_state, "to": t.to_state, "timestamp": t.timestamp, "reason": t.reason}
                        for t in a.history
                    ],
                    "retry_count": a.retry_count,
                }
                for aid, a in self.assets.items()
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_or_create(self, asset_id: str) -> AssetState:
        if asset_id not in self.assets:
            self.assets[asset_id] = AssetState(asset_id=asset_id)
        return self.assets[asset_id]

    def transition(self, asset_id: str, to_state: str, reason: str = "", **metadata) -> bool:
        asset = self.get_or_create(asset_id)
        result = asset.transition(to_state, reason=reason, **metadata)
        self._save()
        return result

    def get_state(self, asset_id: str) -> Optional[str]:
        asset = self.assets.get(asset_id)
        return asset.current_state if asset else None

    def get_stats(self) -> Dict[str, Any]:
        stats = {s: 0 for s in ALL_STATES}
        for asset in self.assets.values():
            stats[asset.current_state] = stats.get(asset.current_state, 0) + 1
        return stats
