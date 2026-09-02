"""Upload Policy Enforcement — BLOCKED gates for live writes.

Gates (hard stops):
- uploads BLOCKED until READY_FOR_CONTROLLED_ACTIVATION
- publishes BLOCKED until READY_FOR_CONTROLLED_ACTIVATION
- deletes BLOCKED
- updates BLOCKED
- no external spend enabled

Idempotency: each operation uses an idempotency key derived from
content identity. Retries after timeout must not create duplicates.
"""
from __future__ import annotations
from enum import Enum
from typing import Optional, Dict, Any
from pathlib import Path
import hashlib


class UploadGate(str, Enum):
    UNCONFIGURED = "UNCONFIGURED"
    BLOCKED = "BLOCKED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    READY_FOR_CONTROLLED_ACTIVATION = "READY_FOR_CONTROLLED_ACTIVATION"


class IdempotencyState(str, Enum):
    RESERVED = "RESERVED"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED_RETRYABLE = "FAILED_RETRYABLE"
    FAILED_TERMINAL = "FAILED_TERMINAL"


class IdempotencyEngine:
    """Prevent duplicate uploads through idempotency keys."""

    def __init__(self, storage_path: Optional[Path] = None):
        # Ensure storage_path is a Path (handles string input from tests)
        from pathlib import Path
        if storage_path is not None and not isinstance(storage_path, Path):
            storage_path = Path(str(storage_path))
        self.storage = storage_path or Path("metrics/idempotency_store.json")
        self.storage.parent.mkdir(parents=True, exist_ok=True)
        self._load()

    def _load(self):
        import json
        self.keys: set = set()
        self.states: Dict[str, str] = {}
        if self.storage.exists():
            try:
                data = json.loads(self.storage.read_text(encoding="utf-8"))
                if isinstance(data.get("keys"), list):
                    self.keys = set(str(k) for k in data["keys"])
                if isinstance(data.get("states"), dict):
                    self.states = {str(k): str(v) for k, v in data["states"].items()}
            except Exception:
                # Fail-closed: malformed file treated as empty
                pass

    def _persist(self):
        import json
        import tempfile
        import os
        data = {"keys": sorted(self.keys), "states": self.states}
        # Atomic write: temporary file -> fsync -> atomic replace
        temp_path = self.storage.with_suffix(self.storage.suffix + ".tmp")
        try:
            temp_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
            # fsync if available (platform-dependent; safe to skip if unavailable)
            try:
                fd = os.open(str(temp_path), os.O_RDWR)
                os.fsync(fd)
                os.close(fd)
            except Exception:
                pass  # fsync optional; atomic rename is the critical part
            # Atomic replace
            temp_path.replace(self.storage)
        except Exception:
            # Fail-closed: do not corrupt state; clean up temp file
            try:
                if temp_path.exists():
                    temp_path.unlink()
            except Exception:
                pass

    def generate_key(
        self,
        campaign_id: str = "",
        video_path: Optional[str] = None,
        title: str = "",
        scheduled_time: Optional[str] = None,
        privacy_status: str = "private",
    ) -> str:
        raw = f"{campaign_id}:{video_path or ''}:{title}:{scheduled_time or ''}:{privacy_status}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def is_duplicate(self, key: str) -> bool:
        return key in self.keys

    def reserve(self, key: str) -> bool:
        """Reserve an idempotency key (state = RESERVED). Returns False if already reserved/succeeded/terminal."""
        if key in self.keys:
            current_state = self.states.get(key, "RESERVED")
            if current_state in ("SUCCEEDED", "FAILED_TERMINAL", "RESERVED"):
                return False
            # For retryable failures or in-progress, allow re-reserve
        else:
            self.keys.add(key)
        self.states[key] = "RESERVED"
        self._persist()
        return True

    def set_state(self, key: str, state: IdempotencyState) -> bool:
        if key not in self.keys:
            return False
        self.states[key] = state.value
        self._persist()
        return True

    def get_state(self, key: str) -> Optional[str]:
        if key not in self.keys:
            return None
        return self.states.get(key, "RESERVED")

    def register(self, key: str) -> bool:
        # Legacy method for backward compatibility; treats register as RESERVED -> IN_PROGRESS -> SUCCEEDED
        if key in self.keys:
            current_state = self.states.get(key, "RESERVED")
            if current_state == "SUCCEEDED":
                return False  # Already completed; duplicate prevented
            if current_state == "FAILED_TERMINAL":
                return False  # Terminal failure; cannot retry
            # For RESERVED/IN_PROGRESS/FAILED_RETRYABLE, allow transition to IN_PROGRESS
            self.states[key] = "IN_PROGRESS"
            self._persist()
            return True
        self.keys.add(key)
        self.states[key] = "RESERVED"
        self._persist()
        return True


class UploadPolicy:
    """Enforce BLOCKED gates for production uploads and publishes."""

    def __init__(self, gate_state: UploadGate = UploadGate.BLOCKED):
        self.gate_state = gate_state
        self.idempotency = IdempotencyEngine()

    def check_upload_allowed(
        self,
        campaign_id: str,
        video_path: Optional[str],
        title: str = "",
        privacy_status: str = "public",
    ) -> Dict[str, Any]:
        result = {
            "allowed": False,
            "gate_state": self.gate_state.value,
            "reason": "",
            "idempotency_key": "",
            "duplicate": False,
        }

        # BLOCKED by default for M-022 readiness
        if self.gate_state != UploadGate.READY_FOR_CONTROLLED_ACTIVATION:
            result["reason"] = f"Upload BLOCKED (gate: {self.gate_state.value}). M-022 readiness requires READY_FOR_CONTROLLED_ACTIVATION."
            result["allowed"] = False
            return result

        # Policy enforcement: public uploads not allowed without explicit authorization
        if privacy_status == "public" and self.gate_state != UploadGate.READY_FOR_CONTROLLED_ACTIVATION:
            result["reason"] = "Public uploads BLOCKED by M-022 upload policy."
            result["allowed"] = False
            return result

        # Idempotency check
        key = self.idempotency.generate_key(
            campaign_id=campaign_id,
            video_path=video_path,
            title=title,
            privacy_status=privacy_status,
        )
        result["idempotency_key"] = key
        if self.idempotency.is_duplicate(key):
            result["duplicate"] = True
            result["reason"] = "Idempotency: duplicate upload prevented."
            result["allowed"] = False
            return result

        # Only allow if gate is READY
        if self.gate_state == UploadGate.READY_FOR_CONTROLLED_ACTIVATION:
            result["allowed"] = True
            result["reason"] = "Controlled activation authorized."
            self.idempotency.register(key)
        else:
            result["reason"] = f"Gate not ready ({self.gate_state.value})."
            result["allowed"] = False
        return result

    def get_gate_description(self) -> str:
        descriptions = {
            UploadGate.UNCONFIGURED: "No authorization configured.",
            UploadGate.BLOCKED: "Live uploads BLOCKED by M-022 readiness policy.",
            UploadGate.READY_FOR_REVIEW: "Ready for review but uploads remain BLOCKED.",
            UploadGate.READY_FOR_CONTROLLED_ACTIVATION: "Controlled activation permitted; uploads allowed.",
        }
        return descriptions.get(self.gate_state, "Unknown gate state.")
