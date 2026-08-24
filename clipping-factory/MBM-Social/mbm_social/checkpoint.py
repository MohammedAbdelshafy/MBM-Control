"""
Campaign checkpoint — persistence + resume for the autonomous runtime.

Stores per-stage structured outputs and the last completed stage index so a
crashed run can resume instead of restarting from source discovery. Each stage
result is recorded with its outputs; on resume the runtime replays already
completed stages from the checkpoint instead of re-executing them.

Checkpoint file layout:
  {
    "campaign_id": str,
    "brand": str,
    "profile": str,
    "mode": str,
    "started_at": str,
    "updated_at": str,
    "completed_stages": [str, ...],
    "outputs": { stage: {...} },        # structured outputs per stage
    "failures": { stage: reason },
    "status": "running" | "completed" | "failed" | "paused"
  }
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


@dataclass
class CampaignCheckpoint:
    campaign_id: str
    brand: str = ""
    profile: str = ""
    mode: str = "internal"
    state_file: Optional[Path] = None
    completed_stages: list[str] = field(default_factory=list)
    outputs: dict[str, Any] = field(default_factory=dict)
    failures: dict[str, str] = field(default_factory=dict)
    status: str = "running"
    started_at: str = ""
    updated_at: str = ""

    _lock = threading.Lock()

    # ── load / save ────────────────────────────────────────────────────
    @classmethod
    def load(cls, state_file: Path) -> "CampaignCheckpoint":
        try:
            data = json.loads(Path(state_file).read_text(encoding="utf-8"))
        except Exception:
            data = {}
        cp = cls(
            campaign_id=data.get("campaign_id", Path(state_file).stem),
            brand=data.get("brand", ""),
            profile=data.get("profile", ""),
            mode=data.get("mode", "internal"),
            state_file=state_file,
            completed_stages=data.get("completed_stages", []),
            outputs=data.get("outputs", {}),
            failures=data.get("failures", {}),
            status=data.get("status", "running"),
            started_at=data.get("started_at", ""),
            updated_at=data.get("updated_at", ""),
        )
        return cp

    def save(self) -> None:
        if not self.state_file:
            return
        self.updated_at = datetime.now(timezone.utc).isoformat()
        if not self.started_at:
            self.started_at = self.updated_at
        with self._lock:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            self.state_file.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    def to_dict(self) -> dict:
        return {
            "campaign_id": self.campaign_id,
            "brand": self.brand,
            "profile": self.profile,
            "mode": self.mode,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "completed_stages": self.completed_stages,
            "outputs": self.outputs,
            "failures": self.failures,
            "status": self.status,
        }

    # ── resume helpers ─────────────────────────────────────────────────
    @property
    def next_stage(self) -> Optional[str]:
        all_stages = [
            "source_discovery", "rights_check", "video_acquisition", "speech_factory",
            "visual_factory", "hook_factory", "ranking", "captions", "thumbnail",
            "quality_control", "publishing_queue", "publisher", "analytics", "learning",
        ]
        for s in all_stages:
            if s not in self.completed_stages:
                return s
        return None

    def is_stage_done(self, stage: str) -> bool:
        return stage in self.completed_stages

    def record(self, stage: str, output: dict, *, failed: bool = False, reason: str = "") -> None:
        with self._lock:
            if failed:
                self.failures[stage] = reason
                # keep partial output for diagnosis
                if output:
                    self.outputs[stage] = output
            else:
                if stage in self.failures:
                    del self.failures[stage]
                self.outputs[stage] = output
                if stage not in self.completed_stages:
                    self.completed_stages.append(stage)
        self.save()

    def mark_completed(self) -> None:
        self.status = "completed"
        self.save()

    def mark_failed(self, reason: str = "") -> None:
        self.status = "failed"
        if reason:
            self.failures.setdefault("_run", reason)
        self.save()

    def mark_paused(self) -> None:
        self.status = "paused"
        self.save()
