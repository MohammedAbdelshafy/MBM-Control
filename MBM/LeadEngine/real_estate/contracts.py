from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any

VALID_STATUSES = {"ok", "blocked", "empty", "malformed"}


class SendState(str, Enum):
    HUMAN_SEND_REQUIRED = "HUMAN_SEND_REQUIRED"
    HUMAN_REVIEW_BLOCKED = "HUMAN_REVIEW_BLOCKED"


class BlockReason(str, Enum):
    CONTACT_UNVERIFIED = "CONTACT_UNVERIFIED"
    BUYER_MARKET_MISMATCH = "BUYER_MARKET_MISMATCH"
    BUYER_MAX_PURCHASE_EXCEEDED = "BUYER_MAX_PURCHASE_EXCEEDED"
    ECONOMIC_GATE_FAILED = "ECONOMIC_GATE_FAILED"


def validate_evidence_status(status: str) -> str:
    value = str(status or "").strip().lower()
    if value not in VALID_STATUSES:
        raise ValueError(f"unsupported evidence status: {status!r}")
    return value


@dataclass(frozen=True)
class PropertyEvidence:
    address: str
    city: str
    state: str
    source_url: str
    source_name: str
    status: str = "ok"
    fields: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", validate_evidence_status(self.status))
        if self.status == "ok" and not self.source_url.strip():
            raise ValueError("source_url is required for usable property evidence")


@dataclass(frozen=True)
class BuyerEvidence:
    name: str
    source_url: str
    source_name: str
    status: str = "ok"
    buy_box: dict[str, Any] = field(default_factory=dict)
    contact: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "status", validate_evidence_status(self.status))
        if self.status == "ok" and not self.source_url.strip():
            raise ValueError("source_url is required for usable buyer evidence")


@dataclass(frozen=True)
class OfferPacket:
    property: PropertyEvidence
    seller: dict[str, Any]
    buyer: BuyerEvidence | None
    underwriting: dict[str, Any]
    offer_price: float
    email_copy: str
    whatsapp_copy: str
    manual_call_payload: dict[str, Any]
    send_state: SendState = SendState.HUMAN_SEND_REQUIRED
    blocked_reasons: list[BlockReason] = field(default_factory=list)
    source_provenance: list[dict[str, Any]] = field(default_factory=list)

    def __post_init__(self) -> None:
        state = self.send_state if isinstance(self.send_state, SendState) else SendState(str(self.send_state))
        reasons = [
            value if isinstance(value, BlockReason) else BlockReason(str(value))
            for value in self.blocked_reasons
        ]
        if state is SendState.HUMAN_SEND_REQUIRED and reasons:
            raise ValueError("blocked_reasons must be empty when send_state is HUMAN_SEND_REQUIRED")
        if state is SendState.HUMAN_REVIEW_BLOCKED and not reasons:
            raise ValueError("blocked_reasons is required when send_state is HUMAN_REVIEW_BLOCKED")
        object.__setattr__(self, "send_state", state)
        object.__setattr__(self, "blocked_reasons", reasons)

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> "OfferPacket":
        prop = data.get("property") or {}
        source_url = str(data.get("source_url") or prop.get("source_url") or "")
        if not source_url.strip():
            raise ValueError("source_url is required")
        property_evidence = PropertyEvidence(
            address=str(prop.get("address") or ""),
            city=str(prop.get("city") or ""),
            state=str(prop.get("state") or ""),
            source_url=source_url,
            source_name=str(prop.get("source_name") or "unknown"),
            status=str(prop.get("status") or "ok"),
            fields=dict(prop.get("fields") or {}),
        )
        seller = dict(data.get("seller") or {})
        return cls(
            property=property_evidence,
            seller=seller,
            buyer=None,
            underwriting=dict(data.get("underwriting") or {}),
            offer_price=float(data.get("offer_price") or 0),
            email_copy=str(data.get("email_copy") or ""),
            whatsapp_copy=str(data.get("whatsapp_copy") or ""),
            manual_call_payload=dict(data.get("manual_call_payload") or {}),
            send_state=SendState(str(data.get("send_state") or SendState.HUMAN_SEND_REQUIRED.value)),
            blocked_reasons=[BlockReason(str(value)) for value in data.get("blocked_reasons") or []],
            source_provenance=list(data.get("source_provenance") or []),
        )
