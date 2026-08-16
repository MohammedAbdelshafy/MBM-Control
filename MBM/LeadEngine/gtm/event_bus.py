"""
GTM EVENT BUS
=============================================================================
Typed, deterministic in-memory event bus for GTM pipeline communication.

Event Types:
  NEW_SIGNAL, NEW_BUYER, PAIN_IDENTIFIED, HOT_BUYER, OUTREACH_READY,
  CALL_CONNECTED, OWNER_CONFIRMED, ADM_CONFIRMED, WRONG_PERSON,
  WRONG_NUMBER, REPLY_RECEIVED, MEETING_BOOKED, MEETING_HELD,
  PROPOSAL_SENT, OBJECTION_RAISED, DEAL_WON, DEAL_LOST
=================================================================================================================
"""

from enum import Enum
from typing import Dict, List, Callable, Any, Optional
from datetime import datetime, timezone
import uuid


class GtmEventType(str, Enum):
    NEW_SIGNAL = "NEW_SIGNAL"
    NEW_BUYER = "NEW_BUYER"
    PAIN_IDENTIFIED = "PAIN_IDENTIFIED"
    HOT_BUYER = "HOT_BUYER"
    OUTREACH_READY = "OUTREACH_READY"
    CALL_CONNECTED = "CALL_CONNECTED"
    OWNER_CONFIRMED = "OWNER_CONFIRMED"
    ADM_CONFIRMED = "ADM_CONFIRMED"
    WRONG_PERSON = "WRONG_PERSON"
    WRONG_NUMBER = "WRONG_NUMBER"
    REPLY_RECEIVED = "REPLY_RECEIVED"
    MEETING_BOOKED = "MEETING_BOOKED"
    MEETING_HELD = "MEETING_HELD"
    PROPOSAL_SENT = "PROPOSAL_SENT"
    OBJECTION_RAISED = "OBJECTION_RAISED"
    DEAL_WON = "DEAL_WON"
    DEAL_LOST = "DEAL_LOST"


class GtmEvent:
    """Immutable, typed event object in the GTM pipeline."""

    def __init__(
        self,
        event_type: GtmEventType,
        entity_id: str,
        producer: str,
        payload: Optional[Dict[str, Any]] = None,
        event_id: Optional[str] = None,
        timestamp: Optional[str] = None,
    ):
        self.event_id = event_id or f"evt_{uuid.uuid4().hex[:12]}"
        self.event_type = event_type
        self.entity_id = entity_id
        self.producer = producer
        self.payload = payload or {}
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "entity_id": self.entity_id,
            "producer": self.producer,
            "payload": self.payload,
            "timestamp": self.timestamp,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GtmEvent":
        return cls(
            event_type=GtmEventType(data["event_type"]),
            entity_id=data["entity_id"],
            producer=data["producer"],
            payload=data.get("payload", {}),
            event_id=data.get("event_id"),
            timestamp=data.get("timestamp"),
        )


class GtmEventBus:
    """Lightweight, deterministic synchronous event bus with audit log history."""

    def __init__(self):
        self._subscribers: Dict[GtmEventType, List[Callable[[GtmEvent], None]]] = {
            t: [] for t in GtmEventType
        }
        self._global_subscribers: List[Callable[[GtmEvent], None]] = []
        self._event_log: List[GtmEvent] = []

    def subscribe(self, event_type: GtmEventType, handler: Callable[[GtmEvent], None]) -> None:
        """Subscribe a handler callback to a specific event type."""
        if handler not in self._subscribers[event_type]:
            self._subscribers[event_type].append(handler)

    def subscribe_all(self, handler: Callable[[GtmEvent], None]) -> None:
        """Subscribe a global handler callback to all event types."""
        if handler not in self._global_subscribers:
            self._global_subscribers.append(handler)

    def unsubscribe(self, event_type: GtmEventType, handler: Callable[[GtmEvent], None]) -> bool:
        """Remove a subscriber handler."""
        if handler in self._subscribers[event_type]:
            self._subscribers[event_type].remove(handler)
            return True
        return False

    def publish(self, event: GtmEvent) -> None:
        """Synchronously publish an event to all subscribers and append to audit log."""
        self._event_log.append(event)

        # Notify specific event subscribers
        for handler in self._subscribers.get(event.event_type, []):
            try:
                handler(event)
            except Exception as e:
                # Isolate handler errors so bus remains deterministic
                print(f"[GtmEventBus Error in {event.event_type.value} handler]: {e}")

        # Notify global subscribers
        for handler in self._global_subscribers:
            try:
                handler(event)
            except Exception as e:
                print(f"[GtmEventBus Error in global handler]: {e}")

    def get_events(
        self,
        event_type: Optional[GtmEventType] = None,
        entity_id: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[GtmEvent]:
        """Query logged events with optional filtering."""
        filtered = self._event_log
        if event_type:
            filtered = [e for e in filtered if e.event_type == event_type]
        if entity_id:
            filtered = [e for e in filtered if e.entity_id == entity_id]
        if limit:
            filtered = filtered[-limit:]
        return filtered

    def clear(self) -> None:
        """Clear the event log and subscribers."""
        self._event_log.clear()
        for k in self._subscribers:
            self._subscribers[k].clear()
        self._global_subscribers.clear()
