"""Provider-neutral revenue/outreach event normalization.

Only observed provider/checkout events may become revenue facts. Unknown or
malformed events fail closed instead of being inferred.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

_ALLOWED = {
    "CALL_STARTED",
    "CONNECTED",
    "NO_ANSWER",
    "WRONG_NUMBER",
    "WRONG_PARTY",
    "INTERESTED",
    "CALLBACK",
    "APPOINTMENT",
    "OFFER_SENT",
    "CHECKOUT_CLICK",
    "PAYMENT_RECEIVED",
    "REFUND",
}


@dataclass(frozen=True)
class RevenueEvent:
    event_id: str
    lead_id: str
    channel: str
    event_type: str
    occurred_at: str
    provider: str
    evidence: str
    verified: bool = False
    amount_usd: float | None = None
    source_event_id: str | None = None

    def validate(self) -> None:
        if not self.event_id.strip():
            raise ValueError("event_id is required")
        if not self.lead_id.strip():
            raise ValueError("lead_id is required")
        if self.event_type not in _ALLOWED:
            raise ValueError(f"unsupported event_type: {self.event_type}")
        if not self.provider.strip():
            raise ValueError("provider is required")
        if not self.evidence.strip():
            raise ValueError("evidence is required")
        datetime.fromisoformat(self.occurred_at.replace("Z", "+00:00"))
        if self.event_type == "PAYMENT_RECEIVED" and self.amount_usd is None:
            raise ValueError("payment event requires amount_usd")

    def as_dict(self) -> dict[str, Any]:
        self.validate()
        return {
            "event_id": self.event_id,
            "lead_id": self.lead_id,
            "channel": self.channel,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at,
            "provider": self.provider,
            "evidence": self.evidence,
            "verified": self.verified,
            "amount_usd": self.amount_usd,
            "source_event_id": self.source_event_id,
        }


def normalize_event(payload: Mapping[str, Any], *, provider: str) -> RevenueEvent:
    """Normalize an external event without inventing missing commercial facts."""
    raw_type = str(payload.get("event_type") or payload.get("type") or "").strip().upper()
    occurred_at = str(payload.get("occurred_at") or payload.get("timestamp") or "").strip()
    if not occurred_at:
        occurred_at = datetime.now(timezone.utc).isoformat()

    event = RevenueEvent(
        event_id=str(payload.get("event_id") or payload.get("id") or "").strip(),
        lead_id=str(payload.get("lead_id") or "").strip(),
        channel=str(payload.get("channel") or "Manual").strip(),
        event_type=raw_type,
        occurred_at=occurred_at,
        provider=provider,
        evidence=str(payload.get("evidence") or payload.get("provider_reference") or "").strip(),
        verified=bool(payload.get("verified", False)),
        amount_usd=(float(payload["amount_usd"]) if payload.get("amount_usd") is not None else None),
        source_event_id=(str(payload["source_event_id"]) if payload.get("source_event_id") else None),
    )
    event.validate()
    return event
