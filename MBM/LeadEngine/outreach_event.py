#!/usr/bin/env python3
"""
Canonical Outreach Event Model — single source of truth for commercial truth.
=============================================================================
ZERO-SIMULATION LAW:
  An outreach_event may ONLY be created from a real-world observation:
    - a real telephony event / human-entered call disposition
    - a real checkout click / payment webhook
    - a real email / SMS delivery event
    - a manually logged human outreach action (with actor + evidence)

  Index position, random choice, fixtures and "realistic defaults" are
  FORBIDDEN as sources. Anything without event evidence counts as ZERO.

Store: append-only JSONL at MBM/LeadEngine/logs/outreach_events.jsonl
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

BASE = Path(__file__).resolve().parent
LOGS = BASE / "logs"
STORE = LOGS / "outreach_events.jsonl"
REVIEW_QUEUE = LOGS / "outreach_events_review.jsonl"

# --- Canonical vocabularies (OX ALPHA vNEXT §2) ---------------------------

CALL_DISPOSITIONS = {
    "CONNECTED_OWNER",
    "CONNECTED_DECISION_MAKER",
    "WRONG_NUMBER",
    "WRONG_PARTY",
    "DISCONNECTED",
    "NO_ANSWER",
    "VOICEMAIL",
    "DO_NOT_CALL",
    "INTERESTED",
    "NOT_INTERESTED",
    "CALLBACK",
    "QUALIFIED",
    "APPOINTMENT_BOOKED",
}

COMMERCIAL_EVENTS = {
    "OFFER_SENT",
    "CHECKOUT_CLICK",
    "PAYMENT_RECEIVED",
    "REFUND",
    "CHARGEBACK",
}

ALLOWED_DISPOSITIONS = CALL_DISPOSITIONS | COMMERCIAL_EVENTS

CHANNELS = {"phone", "email", "sms", "whatsapp", "social", "checkout", "manual"}

# Dispositions that constitute a real conversation with a human.
CONVERSATION_DISPOSITIONS = {
    "CONNECTED_OWNER",
    "CONNECTED_DECISION_MAKER",
    "INTERESTED",
    "QUALIFIED",
    "APPOINTMENT_BOOKED",
}


class DispositionError(ValueError):
    """Raised when an event would violate the zero-simulation law."""


@dataclass
class OutreachEvent:
    event_id: str
    lead_id: str
    channel: str
    timestamp: str
    actor: str
    disposition: str
    provider: str = ""
    evidence: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    campaign_id: str = ""
    notes: str = ""

    def validate(self) -> None:
        if not self.event_id:
            raise DispositionError("event_id is required")
        if not self.lead_id:
            raise DispositionError("lead_id is required")
        if self.channel not in CHANNELS:
            raise DispositionError(f"channel '{self.channel}' not allowed")
        if not self.actor:
            raise DispositionError("actor is required (who observed/recorded this)")
        if self.disposition not in ALLOWED_DISPOSITIONS:
            raise DispositionError(
                f"disposition '{self.disposition}' is not a canonical outcome; "
                f"synthetic outcomes are forbidden"
            )
        try:
            datetime.fromisoformat(self.timestamp.replace("Z", "+00:00"))
        except Exception:
            raise DispositionError(f"timestamp '{self.timestamp}' is not ISO8601")

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def make_event_id(*parts: Any) -> str:
    digest = hashlib.sha256("|".join(str(p) for p in parts).encode("utf-8")).hexdigest()
    return f"evt_{digest[:24]}"


def record_event(event: OutreachEvent, store: Optional[Path] = None) -> OutreachEvent:
    """Validate + append one canonical event. Idempotent by event_id."""
    # Resolve at call time so test suites can isolate the store (conftest).
    store = store or STORE
    event.validate()
    store.parent.mkdir(parents=True, exist_ok=True)
    if store.exists():
        for line in store.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                existing = json.loads(line)
            except json.JSONDecodeError:
                continue
            if existing.get("event_id") == event.event_id:
                return event
    with store.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event.to_dict(), default=str) + "\n")
    return event


def load_events(day: Optional[str] = None, store: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Load events, optionally filtered to a YYYY-MM-DD day (UTC)."""
    # Resolve at call time so test suites can isolate the store (conftest).
    store = store or STORE
    if not store.exists():
        return []
    events = []
    for line in store.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if day and not str(ev.get("timestamp", "")).startswith(day):
            continue
        events.append(ev)
    events.sort(key=lambda e: e.get("timestamp", ""))
    return events


def funnel_counts(events: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    """Derive scoreboard counters from canonical events ONLY."""
    counts = {
        "calls_attempted": 0,
        "connected": 0,
        "conversations": 0,
        "wrong_numbers": 0,
        "wrong_parties": 0,
        "no_answers": 0,
        "voicemails": 0,
        "do_not_call": 0,
        "callbacks": 0,
        "qualified": 0,
        "appointments": 0,
        "offers_sent": 0,
    }
    for ev in events:
        d = ev.get("disposition")
        if d in COMMERCIAL_EVENTS:
            if d == "OFFER_SENT":
                counts["offers_sent"] += 1
            continue
        counts["calls_attempted"] += 1
        if d in CONVERSATION_DISPOSITIONS:
            counts["connected"] += 1
            counts["conversations"] += 1
        if d == "QUALIFIED":
            counts["qualified"] += 1
        if d == "APPOINTMENT_BOOKED":
            counts["appointments"] += 1
        if d == "WRONG_NUMBER":
            counts["wrong_numbers"] += 1
        elif d == "WRONG_PARTY":
            counts["wrong_parties"] += 1
        elif d == "NO_ANSWER":
            counts["no_answers"] += 1
        elif d == "VOICEMAIL":
            counts["voicemails"] += 1
        elif d == "DO_NOT_CALL":
            counts["do_not_call"] += 1
        elif d == "CALLBACK":
            counts["callbacks"] += 1
    return counts


# --- Legacy import adapters (conservative, never upgrade meaning) ----------

_CLOSE_MAP = {
    "answered": None,  # party unidentified -> review queue, never CONNECTED_*
    "voicemail": "VOICEMAIL",
    "no-answer": "NO_ANSWER",
    "bad-number": "DISCONNECTED",
    "skipped": None,
    "dnc": "DO_NOT_CALL",
}

_CALL_KEYWORDS = [
    ("do not call", "DO_NOT_CALL"),
    ("dnc", "DO_NOT_CALL"),
    ("wrong number", "WRONG_NUMBER"),
    ("not interested", "NOT_INTERESTED"),
    ("callback", "CALLBACK"),
    ("call back", "CALLBACK"),
    ("booked", "APPOINTMENT_BOOKED"),
    ("scheduled", "APPOINTMENT_BOOKED"),
    ("appointment", "APPOINTMENT_BOOKED"),
    ("demo booked", "APPOINTMENT_BOOKED"),
    ("proposal", "OFFER_SENT"),
    ("qualified", "QUALIFIED"),
    ("interested", "INTERESTED"),
    ("voicemail", "VOICEMAIL"),
    ("no answer", "NO_ANSWER"),
]


def _map_legacy(outcome_text: str) -> Optional[str]:
    text = (outcome_text or "").strip().lower()
    for keyword, mapped in _CALL_KEYWORDS:
        if keyword in text:
            return mapped
    return None


def import_legacy_dispositions(
    store: Optional[Path] = None,
    review_path: Optional[Path] = None,
    close_log: Optional[Path] = None,
    call_log: Optional[Path] = None,
) -> Dict[str, int]:
    """
    Convert legacy REAL human disposition logs into canonical events.

    Ambiguous rows (e.g. 'answered' with no party identification) are routed
    to the review queue instead of being guessed. CLOSED_WON is NEVER imported
    as PAYMENT_RECEIVED without checkout evidence.
    """
    # Resolve at call time so test suites can isolate the store (conftest).
    store = store or STORE
    review_path = review_path or REVIEW_QUEUE
    stats = {"imported": 0, "review": 0}
    close_log = close_log or (LOGS / "close_dispositions.json")
    call_log = call_log or (LOGS / "call_dispositions.json")

    imported_ids = set()
    if store.exists():
        for line in store.read_text(encoding="utf-8").splitlines():
            try:
                imported_ids.add(json.loads(line).get("event_id"))
            except json.JSONDecodeError:
                pass

    def write(path: Path, payload: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(payload, default=str) + "\n")

    if close_log.exists():
        try:
            rows = json.loads(close_log.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            rows = []
        for i, row in enumerate(rows):
            raw = str(row.get("outcome", "")).lower()
            eid = make_event_id("close", row.get("timestamp"), row.get("phone"), i)
            if eid in imported_ids:
                continue
            mapped = _CLOSE_MAP.get(raw)
            if mapped is None:
                write(review_path, {**row, "_review_reason": f"unmappable close outcome '{raw}'", "_event_id": eid})
                stats["review"] += 1
                continue
            record_event(OutreachEvent(
                event_id=eid,
                lead_id=row.get("phone") or f"close-{i}",
                channel="phone",
                timestamp=row.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                actor="close_queue_dialer",
                disposition=mapped,
                provider="twilio_bridge",
                evidence={"file": str(close_log.name), "company": row.get("company"), "detail": row.get("detail")},
                source="legacy_close_dispositions",
                notes=f"raw_outcome={raw}",
            ), store)
            stats["imported"] += 1

    if call_log.exists():
        try:
            rows = json.loads(call_log.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            rows = []
        for i, row in enumerate(rows):
            raw = str(row.get("disposition", ""))
            eid = make_event_id("callapi", row.get("timestamp") or row.get("logged_at"), row.get("lead_id"), i)
            if eid in imported_ids:
                continue
            mapped = _map_legacy(raw)
            if mapped in ("PAYMENT_RECEIVED",):
                write(review_path, {**row, "_review_reason": "payment requires checkout evidence", "_event_id": eid})
                stats["review"] += 1
                continue
            if mapped is None:
                write(review_path, {**row, "_review_reason": f"unmappable call disposition '{raw}'", "_event_id": eid})
                stats["review"] += 1
                continue
            channel = "email" if "@" in str(row.get("prospect_name", "")) else "phone"
            record_event(OutreachEvent(
                event_id=eid,
                lead_id=str(row.get("lead_id") or f"call-{i}"),
                channel=channel,
                timestamp=row.get("timestamp") or row.get("logged_at") or datetime.now(timezone.utc).isoformat(),
                actor="express_api_operator",
                disposition=mapped,
                provider="manual_disposition_ui",
                evidence={"file": str(call_log.name), "notes": row.get("notes"), "callback_time": row.get("callback_time")},
                source="legacy_call_dispositions",
                notes=f"raw_disposition={raw}",
            ), store)
            stats["imported"] += 1

    return stats


if __name__ == "__main__":
    stats = import_legacy_dispositions()
    day = date.today().isoformat()
    todays = load_events(day=day)
    print(f"legacy_import: {stats}")
    print(f"canonical_events_today({day}): {len(todays)}")
    print(f"funnel: {funnel_counts(load_events())}")
