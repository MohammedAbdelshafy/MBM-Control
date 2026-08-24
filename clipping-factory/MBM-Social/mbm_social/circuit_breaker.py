"""
Circuit breaker + dead-letter queue for publishing reliability (Phase 13).

CircuitBreaker guards each publisher (keyed by platform). After `failure_threshold`
consecutive failures within a window it opens and fast-fails subsequent calls
until `cooldown_sec` elapses, then half-opens for a single trial.

Dead-letter routing: packages that exhaust publisher retries (or are flagged
BLOCKED/MANUAL_REQUIRED) are moved into `publish_queue/dead_letter/` so they
are never silently dropped and never auto-retried into failure.
"""
from __future__ import annotations

import json
import shutil
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

CLOSED = "closed"
OPEN = "open"
HALF_OPEN = "half_open"


@dataclass
class BreakerState:
    key: str
    state: str = CLOSED
    failures: int = 0
    opened_at: float = 0.0
    half_open_at: float = 0.0
    last_failure_at: float = 0.0


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 3,
        cooldown_sec: int = 1800,
        window_sec: int = 3600,
    ):
        self.failure_threshold = failure_threshold
        self.cooldown_sec = cooldown_sec
        self.window_sec = window_sec
        self._states: dict[str, BreakerState] = {}
        self._lock = threading.Lock()

    def _state(self, key: str) -> BreakerState:
        if key not in self._states:
            self._states[key] = BreakerState(key=key)
        return self._states[key]

    def allow(self, key: str) -> bool:
        with self._lock:
            st = self._state(key)
            now = time.time()
            if st.state == CLOSED:
                return True
            if st.state == OPEN:
                if now - st.opened_at >= self.cooldown_sec:
                    st.state = HALF_OPEN
                    st.half_open_at = now
                    return True
                return False
            # HALF_OPEN: allow exactly one trial
            return True

    def success(self, key: str) -> None:
        with self._lock:
            st = self._state(key)
            st.failures = 0
            st.state = CLOSED

    def failure(self, key: str) -> None:
        with self._lock:
            st = self._state(key)
            now = time.time()
            # Window expiry: if the last failure was long ago and we are still
            # closed, forget the old failures before counting this one.
            if st.state == CLOSED and st.failures > 0 and (now - st.last_failure_at) > self.window_sec:
                st.failures = 0
            st.failures += 1
            st.last_failure_at = now
            if st.state == HALF_OPEN:
                st.state = OPEN
                st.opened_at = now
            elif st.failures >= self.failure_threshold:
                st.state = OPEN
                st.opened_at = now

    def status(self, key: str) -> str:
        with self._lock:
            return self._state(key).state


def move_to_dead_letter(package_path: Path, queue_dir: Path, reason: str, detail: Optional[dict] = None) -> Path:
    """Move a failed/publish-blocked package to the dead-letter subfolder.

    Never deletes; preserves the package + reason so a human (or a night op)
    can recover it. Returns the destination path.
    """
    package_path = Path(package_path)
    dl_dir = Path(queue_dir) / "dead_letter"
    dl_dir.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(package_path.read_text(encoding="utf-8"))
    except Exception:
        data = {}
    data = data if isinstance(data, dict) else {}
    data["status"] = "dead_letter"
    data.setdefault("dead_letter", {})["reason"] = reason
    data.setdefault("dead_letter", {})["at"] = datetime.now(timezone.utc).isoformat()
    if detail:
        data["dead_letter"]["detail"] = detail
    dest = dl_dir / package_path.name
    dest.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    # Remove from active queue only after a verified copy exists.
    try:
        package_path.unlink()
    except Exception:
        pass
    return dest
