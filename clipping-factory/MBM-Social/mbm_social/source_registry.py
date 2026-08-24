"""
Source registry — the Phase 2 source/campaign intake lifecycle.

Enforces the rights/approval gate BEFORE any acquisition or processing happens.
A restricted source may NOT be processed until it is in the APPROVED state.

Lifecycle:
  DISCOVERED -> APPROVAL_REQUIRED -> APPROVED -> ACQUISITION
  -> PROCESSING -> COMPLETE -> ARCHIVED

Failure/hold states: BLOCKED (rights denied / restricted + not approved),
REJECTED (manual rejection). Unapproved restricted sources are never returned
by get_next_processable().
"""
from __future__ import annotations

import json
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

DISCOVERED = "DISCOVERED"
APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
APPROVED = "APPROVED"
ACQUISITION = "ACQUISITION"
PROCESSING = "PROCESSING"
COMPLETE = "COMPLETE"
ARCHIVED = "ARCHIVED"
BLOCKED = "BLOCKED"
REJECTED = "REJECTED"

TERMINAL = {ARCHIVED, REJECTED, BLOCKED}


@dataclass
class SourceRecord:
    source_id: str
    url: str
    brand: str
    source_type: str = "manual"
    restricted: bool = False            # e.g. copyrighted / third-party owned
    rights_status: str = "unknown"      # "unknown" | "cleared" | "licensed" | "owned"
    state: str = DISCOVERED
    approved_by: str = ""
    approved_at: str = ""
    campaign_id: str = ""
    meta: dict = field(default_factory=dict)
    history: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "source_id": self.source_id,
            "url": self.url,
            "brand": self.brand,
            "source_type": self.source_type,
            "restricted": self.restricted,
            "rights_status": self.rights_status,
            "state": self.state,
            "approved_by": self.approved_by,
            "approved_at": self.approved_at,
            "campaign_id": self.campaign_id,
            "meta": self.meta,
            "history": self.history,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "SourceRecord":
        return cls(
            source_id=d["source_id"], url=d.get("url", ""), brand=d.get("brand", ""),
            source_type=d.get("source_type", "manual"), restricted=bool(d.get("restricted", False)),
            rights_status=d.get("rights_status", "unknown"), state=d.get("state", DISCOVERED),
            approved_by=d.get("approved_by", ""), approved_at=d.get("approved_at", ""),
            campaign_id=d.get("campaign_id", ""), meta=d.get("meta", {}),
            history=d.get("history", []),
        )


class SourceRegistry:
    def __init__(self, store_path: Optional[Path] = None):
        self.store_path = Path(store_path) if store_path else None
        self._records: dict[str, SourceRecord] = {}
        self._lock = threading.Lock()
        self.load()

    # ── persistence ────────────────────────────────────────────────────
    def load(self) -> None:
        if not self.store_path or not self.store_path.exists():
            return
        try:
            data = json.loads(self.store_path.read_text(encoding="utf-8"))
        except Exception:
            return
        with self._lock:
            self._records = {k: SourceRecord.from_dict(v) for k, v in data.get("sources", {}).items()}

    def save(self) -> None:
        if not self.store_path:
            return
        with self._lock:
            self.store_path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"updated": datetime.now(timezone.utc).isoformat(),
                       "sources": {k: v.to_dict() for k, v in self._records.items()}}
            self.store_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # ── registration / approval ────────────────────────────────────────
    def register(self, url: str, brand: str, *, source_type: str = "manual",
                 restricted: bool = False, rights_status: str = "unknown",
                 campaign_id: str = "", source_id: Optional[str] = None) -> SourceRecord:
        sid = source_id or f"src_{abs(hash((url, brand))) % 10**12}"
        rec = SourceRecord(
            source_id=sid, url=url, brand=brand, source_type=source_type,
            restricted=restricted, rights_status=rights_status,
            campaign_id=campaign_id,
            # Restricted sources require explicit approval; others self-approve.
            state=APPROVAL_REQUIRED if restricted else APPROVED,
        )
        rec.history.append({"at": datetime.now(timezone.utc).isoformat(),
                            "event": "registered", "state": rec.state})
        with self._lock:
            self._records[sid] = rec
        self.save()
        return rec

    def request_approval(self, source_id: str) -> SourceRecord:
        rec = self._get(source_id)
        if rec.state in (DISCOVERED,):
            rec.state = APPROVAL_REQUIRED
            rec.history.append({"at": datetime.now(timezone.utc).isoformat(), "event": "approval_requested"})
            self.save()
        return rec

    def approve(self, source_id: str, approved_by: str, rights_status: str = "cleared") -> SourceRecord:
        rec = self._get(source_id)
        rec.state = APPROVED
        rec.approved_by = approved_by
        rec.approved_at = datetime.now(timezone.utc).isoformat()
        rec.rights_status = rights_status
        rec.history.append({"at": rec.approved_at, "event": "approved", "by": approved_by})
        self.save()
        return rec

    def reject(self, source_id: str, reason: str = "") -> SourceRecord:
        rec = self._get(source_id)
        rec.state = REJECTED
        rec.history.append({"at": datetime.now(timezone.utc).isoformat(), "event": "rejected", "reason": reason})
        self.save()
        return rec

    def block(self, source_id: str, reason: str = "") -> SourceRecord:
        rec = self._get(source_id)
        rec.state = BLOCKED
        rec.history.append({"at": datetime.now(timezone.utc).isoformat(), "event": "blocked", "reason": reason})
        self.save()
        return rec

    # ── gating ─────────────────────────────────────────────────────────
    def is_processable(self, source_id: str) -> bool:
        """True only if the source reached APPROVED (rights cleared)."""
        rec = self._get(source_id)
        return rec.state == APPROVED

    def assert_processable(self, source_id: str) -> None:
        """Raise if the source must not be acquired/processed yet."""
        rec = self._get(source_id)
        if rec.state != APPROVED:
            raise RuntimeError(
                f"Source {source_id} is '{rec.state}' — cannot process. "
                f"Restricted sources require APPROVED rights status."
            )

    def advance(self, source_id: str, to_state: str) -> SourceRecord:
        rec = self._get(source_id)
        rec.state = to_state
        rec.history.append({"at": datetime.now(timezone.utc).isoformat(), "event": "advance", "to": to_state})
        self.save()
        return rec

    def get_next_processable(self, brand: Optional[str] = None) -> Optional[SourceRecord]:
        with self._lock:
            candidates = [r for r in self._records.values() if r.state == APPROVED]
            if brand:
                candidates = [r for r in candidates if r.brand == brand]
            if not candidates:
                return None
            return sorted(candidates, key=lambda r: r.approved_at or "")[0]

    def pending_approval(self, brand: Optional[str] = None) -> list[SourceRecord]:
        with self._lock:
            out = [r for r in self._records.values() if r.state == APPROVAL_REQUIRED]
            if brand:
                out = [r for r in out if r.brand == brand]
            return out

    def get(self, source_id: str) -> Optional[SourceRecord]:
        return self._get(source_id)

    def _get(self, source_id: str) -> SourceRecord:
        with self._lock:
            rec = self._records.get(source_id)
        if not rec:
            raise KeyError(f"Unknown source_id: {source_id}")
        return rec
