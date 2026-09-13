from __future__ import annotations

from .contracts import BuyerEvidence, PropertyEvidence


def normalize_scrapling_record(record: dict[str, object]) -> PropertyEvidence:
    status = str(record.get("status") or "ok").lower()
    source_url = str(record.get("url") or record.get("source_url") or "")
    source_name = str(record.get("source") or record.get("source_name") or "scrapling")
    return PropertyEvidence(
        address=str(record.get("address") or ""),
        city=str(record.get("city") or ""),
        state=str(record.get("state") or ""),
        source_url=source_url,
        source_name=source_name,
        status=status,
        fields=dict(record.get("fields") or {}),
    )


def normalize_scrapling_batch(records: list[dict[str, object]]) -> list[PropertyEvidence]:
    return [normalize_scrapling_record(record) for record in records]


def normalize_buyer_record(record: dict[str, object], source_name: str = "vibe-prospecting") -> BuyerEvidence:
    return BuyerEvidence(
        name=str(record.get("name") or ""),
        source_url=str(record.get("url") or record.get("source_url") or ""),
        source_name=source_name,
        status=str(record.get("status") or "ok"),
        buy_box=dict(record.get("buy_box") or {}),
        contact=dict(record.get("contact") or {}),
    )
