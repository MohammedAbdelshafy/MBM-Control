from __future__ import annotations

from datetime import datetime, timezone

import pytest

from MBM.LeadEngine.connectors.events import RevenueEvent, normalize_event
from MBM.LeadEngine.connectors.evidence import build_evidence
from MBM.LeadEngine.airtable_contract_sync import to_airtable_fields


def test_evidence_requires_source_and_timestamp() -> None:
    envelope = build_evidence(
        "LEAD-1",
        "clay",
        {"company": "Example LLC"},
        source="company-site",
        confidence="HIGH",
        observed_at=datetime.now(timezone.utc).isoformat(),
    )
    assert envelope.as_dict()["lead_id"] == "LEAD-1"
    assert envelope.as_dict()["evidence"][0]["source"] == "company-site"


def test_airtable_mapping_requires_stable_lead_id() -> None:
    with pytest.raises(ValueError):
        to_airtable_fields({"company": "No ID"})


def test_airtable_mapping_does_not_write_safety_fields() -> None:
    fields = to_airtable_fields(
        {
            "lead_id": "LEAD-2",
            "company": "Example LLC",
            "phone": "+15550001111",
            "verified_phone": True,
            "dnc": True,
            "segment": "HEALTHCARE_CLINIC",
            "script_id": "SCRIPT-1",
        }
    )
    assert fields["Lead ID"] == "LEAD-2"
    assert "Verified Phone" not in fields
    assert "DNC" not in fields
    assert "Suppressed" not in fields


def test_revenue_event_requires_evidence() -> None:
    with pytest.raises(ValueError):
        RevenueEvent(
            event_id="evt-1",
            lead_id="LEAD-3",
            channel="Call",
            event_type="CONNECTED",
            occurred_at=datetime.now(timezone.utc).isoformat(),
            provider="Phound",
            evidence="",
        ).validate()


def test_revenue_event_rejects_unknown_event() -> None:
    payload = {
        "event_id": "evt-2",
        "lead_id": "LEAD-3",
        "type": "MEETING_BOOKED_BY_INDEX",
        "channel": "Call",
        "provider_reference": "test",
    }
    with pytest.raises(ValueError):
        normalize_event(payload, provider="test")


def test_payment_requires_amount() -> None:
    with pytest.raises(ValueError):
        RevenueEvent(
            event_id="evt-3",
            lead_id="LEAD-4",
            channel="Payment",
            event_type="PAYMENT_RECEIVED",
            occurred_at=datetime.now(timezone.utc).isoformat(),
            provider="Whop",
            evidence="purchase-webhook",
        ).validate()
