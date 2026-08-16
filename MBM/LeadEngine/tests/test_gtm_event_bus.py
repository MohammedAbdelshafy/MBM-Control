"""
TESTS: GTM EVENT BUS
=============================================================================
Hermetic unit tests verifying:
1. Typed event creation and serialization
2. Subscription and synchronous publishing
3. Global event listeners
4. Error isolation across handlers
5. Querying and audit log filtering
=============================================================================
"""

import sys
from pathlib import Path
import pytest

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.gtm.event_bus import GtmEvent, GtmEventType, GtmEventBus


def test_gtm_event_creation_and_dict():
    """Verify GtmEvent instantiation and dictionary roundtrip."""
    event = GtmEvent(
        event_type=GtmEventType.NEW_BUYER,
        entity_id="BUYER-123",
        producer="TEST_RUNNER",
        payload={"score": 95, "company": "Summit HVAC"},
    )
    assert event.event_type == GtmEventType.NEW_BUYER
    assert event.entity_id == "BUYER-123"
    assert event.payload["score"] == 95
    
    d = event.to_dict()
    reconstructed = GtmEvent.from_dict(d)
    assert reconstructed.event_id == event.event_id
    assert reconstructed.event_type == event.event_type


def test_event_bus_pub_sub():
    """Verify event bus delivers events to subscribed handlers."""
    bus = GtmEventBus()
    received = []

    def on_hot_buyer(evt: GtmEvent):
        received.append(evt)

    bus.subscribe(GtmEventType.HOT_BUYER, on_hot_buyer)

    # Publish matching event
    e1 = GtmEvent(GtmEventType.HOT_BUYER, entity_id="H1", producer="PRODUCER")
    bus.publish(e1)
    assert len(received) == 1
    assert received[0].entity_id == "H1"

    # Publish non-matching event
    e2 = GtmEvent(GtmEventType.WRONG_PERSON, entity_id="W1", producer="PRODUCER")
    bus.publish(e2)
    assert len(received) == 1


def test_global_subscriber_and_error_isolation():
    """Verify global subscribers receive all events and handler errors do not break the bus."""
    bus = GtmEventBus()
    all_events = []

    def faulty_handler(evt: GtmEvent):
        raise RuntimeError("Handler failed on purpose")

    def safe_global(evt: GtmEvent):
        all_events.append(evt)

    bus.subscribe(GtmEventType.CALL_CONNECTED, faulty_handler)
    bus.subscribe_all(safe_global)

    e = GtmEvent(GtmEventType.CALL_CONNECTED, entity_id="CALL-01", producer="VOICE")
    bus.publish(e)

    assert len(all_events) == 1
    assert all_events[0].entity_id == "CALL-01"
    assert len(bus.get_events()) == 1


def test_event_bus_filtering():
    """Verify querying logged events by type and entity_id."""
    bus = GtmEventBus()
    bus.publish(GtmEvent(GtmEventType.NEW_SIGNAL, entity_id="E1", producer="P1"))
    bus.publish(GtmEvent(GtmEventType.PAIN_IDENTIFIED, entity_id="E1", producer="P2"))
    bus.publish(GtmEvent(GtmEventType.NEW_SIGNAL, entity_id="E2", producer="P1"))

    e1_events = bus.get_events(entity_id="E1")
    assert len(e1_events) == 2

    signals = bus.get_events(event_type=GtmEventType.NEW_SIGNAL)
    assert len(signals) == 2
