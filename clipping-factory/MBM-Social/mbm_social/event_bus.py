"""
Event bus — append-only, observable event stream for the clipping pipeline.

Every pipeline stage emits a structured event here. Events are written to a
JSONL file (one object per line) and dispatched to optional in-process
observers. This is the single observability surface required by the M-022
production contract (no stage is silent).

Event schema:
  {
    "event_id": str,            # deterministic uuid
    "ts": str,                  # ISO-8601 UTC
    "type": str,                # "stage.start" | "stage.result" | "publish" | ...
    "campaign_id": str,
    "stage": str,
    "status": "ok" | "fail" | "info",
    "duration_sec": float,
    "metrics": {...},           # runtime metrics recorded by the stage
    "reason": str,              # failure reason when status == "fail"
    "data": {...}               # arbitrary structured output
  }
"""
from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

EventType = str


@dataclass
class Event:
    event_id: str
    ts: str
    type: str
    campaign_id: str
    stage: str
    status: str
    duration_sec: float = 0.0
    reason: str = ""
    metrics: dict = field(default_factory=dict)
    data: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "ts": self.ts,
            "type": self.type,
            "campaign_id": self.campaign_id,
            "stage": self.stage,
            "status": self.status,
            "duration_sec": round(self.duration_sec, 3),
            "reason": self.reason,
            "metrics": self.metrics,
            "data": self.data,
        }


_Observer = Callable[[Event], None]


class EventBus:
    def __init__(self, log_path: Optional[Path] = None):
        self.log_path = Path(log_path) if log_path else None
        self._lock = threading.Lock()
        self._observers: list[_Observer] = []

    # ── observer registration ──────────────────────────────────────────
    def subscribe(self, fn: _Observer) -> None:
        with self._lock:
            self._observers.append(fn)

    # ── emission ───────────────────────────────────────────────────────
    def emit(
        self,
        type: EventType,
        campaign_id: str,
        stage: str,
        status: str = "info",
        *,
        duration_sec: float = 0.0,
        reason: str = "",
        metrics: Optional[dict] = None,
        data: Optional[dict] = None,
    ) -> Event:
        ev = Event(
            event_id=uuid.uuid4().hex,
            ts=datetime.now(timezone.utc).isoformat(),
            type=type,
            campaign_id=campaign_id,
            stage=stage,
            status=status,
            duration_sec=duration_sec,
            reason=reason,
            metrics=metrics or {},
            data=data or {},
        )
        with self._lock:
            if self.log_path:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(ev.to_dict(), ensure_ascii=False) + "\n")
            for obs in self._observers:
                try:
                    obs(ev)
                except Exception:
                    # Observers must never break the pipeline.
                    pass
        return ev

    def stage_start(self, campaign_id: str, stage: str) -> Event:
        return self.emit("stage.start", campaign_id, stage, status="info")

    def stage_result(
        self,
        campaign_id: str,
        stage: str,
        success: bool,
        *,
        duration_sec: float = 0.0,
        reason: str = "",
        metrics: Optional[dict] = None,
        data: Optional[dict] = None,
    ) -> Event:
        return self.emit(
            "stage.result",
            campaign_id,
            stage,
            status="ok" if success else "fail",
            duration_sec=duration_sec,
            reason=reason,
            metrics=metrics,
            data=data,
        )

    def publish(self, campaign_id: str, stage: str, data: dict) -> Event:
        return self.emit("publish", campaign_id, stage, status="ok", data=data)

    # ── replay / inspection ────────────────────────────────────────────
    def events(self, campaign_id: Optional[str] = None) -> list[dict]:
        if not self.log_path or not self.log_path.exists():
            return []
        out = []
        with open(self.log_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    ev = json.loads(line)
                except Exception:
                    continue
                if campaign_id and ev.get("campaign_id") != campaign_id:
                    continue
                out.append(ev)
        return out


# Process-global default bus; modules may instantiate their own.
_default_bus: Optional[EventBus] = None


def default_bus(log_path: Optional[Path] = None) -> EventBus:
    global _default_bus
    if _default_bus is None:
        if log_path is None:
            from pathlib import Path as _P
            log_path = _P(__file__).resolve().parent.parent / "artifacts" / "events.jsonl"
        _default_bus = EventBus(log_path)
    return _default_bus
