#!/usr/bin/env python3
"""
Promote New Verified Leads to the Top of Their Dialer Category
==============================================================
Safe, idempotent post-processing for the canonical dialer DB.

Rules:
- Never admit unverified or suppressed records.
- Preserve every existing lead object and sales-history field.
- Detect freshness from common ingestion/discovery timestamp fields.
- Newer verified leads rank ahead of older leads inside the same vertical.
- Within the fresh cohort, use priority/callability/lead score as tie-breakers.
- Existing category structure is preserved.
- Running this script repeatedly produces the same ordering.

This script reorders the already-reconciled dialer DB. It does not add
PII to Git and does not fabricate leads or phone numbers.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIALER_DB_PATH = ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"

_TIMESTAMP_FIELDS = (
    "created_at", "createdAt", "found_at", "foundAt", "discovered_at", "discoveredAt",
    "ingested_at", "ingestedAt", "updated_at", "updatedAt", "first_seen_at", "firstSeenAt",
    "source_fetched_at", "sourceFetchedAt", "observed_at", "observedAt",
)
_DETAIL_TIMESTAMP_FIELDS = (
    "created_at", "createdAt", "found_at", "foundAt", "discovered_at", "discoveredAt",
    "ingested_at", "ingestedAt", "updated_at", "updatedAt", "first_seen_at", "firstSeenAt",
    "generated_at", "generatedAt", "source_fetched_at", "sourceFetchedAt", "observed_at", "observedAt",
)


def normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", str(phone or ""))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def parse_timestamp(value) -> float:
    if not value:
        return 0.0
    text = str(value).strip()
    if not text:
        return 0.0
    try:
        text = text.replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except Exception:
        return 0.0


def freshness_epoch(lead: dict) -> float:
    stamps = []
    for field in _TIMESTAMP_FIELDS:
        if field in lead:
            stamps.append(parse_timestamp(lead.get(field)))
    details = lead.get("details") or {}
    if isinstance(details, dict):
        for field in _DETAIL_TIMESTAMP_FIELDS:
            if field in details:
                stamps.append(parse_timestamp(details.get(field)))
    return max(stamps or [0.0])


def is_verified(lead: dict) -> bool:
    phone = normalize_phone(lead.get("phone"))
    if len(phone) != 10:
        return False
    status = str(lead.get("skip_trace_status") or lead.get("verification_status") or "").upper()
    confidence = str(lead.get("skip_trace_confidence") or lead.get("contact_confidence") or "").lower()
    details = lead.get("details") or {}
    source = str(details.get("source") or lead.get("source") or "").lower() if isinstance(details, dict) else ""
    return (
        status == "VERIFIED"
        or confidence in {"high", "verified"}
        or bool(details.get("verified_phone")) if isinstance(details, dict) else False
    ) or any(token in source for token in ("dcad", "county", "npi", "skip trace", "verified"))


def is_suppressed(lead: dict) -> bool:
    state = str(lead.get("identity_state") or "").upper()
    return state in {"WRONG_PERSON", "WRONG_NUMBER", "TENANT", "DO_NOT_CALL", "RELATIVE_OR_ASSOCIATE", "QUARANTINED", "DNC", "BAD_NUMBER", "NON_OWNER"}


def priority_value(lead: dict) -> int:
    details = lead.get("details") or {}
    raw = lead.get("priority", details.get("priority", 9) if isinstance(details, dict) else 9)
    try:
        return int(raw)
    except Exception:
        return 9


def score_value(lead: dict, *keys: str) -> int:
    for key in keys:
        try:
            value = int(lead.get(key) or 0)
            if value:
                return value
        except Exception:
            continue
    return 0


def category_key(lead: dict) -> str:
    return str(lead.get("vertical") or lead.get("vertical_tag") or (lead.get("details") or {}).get("vertical_tag") or "Uncategorized")


def lead_sort_key(lead: dict):
    fresh = freshness_epoch(lead)
    return (
        -int(fresh > 0),
        -fresh,
        priority_value(lead),
        -score_value(lead, "callability_score", "contact_confidence_score", "deal_score", "motivation_score", "score"),
        str(lead.get("company") or lead.get("contact") or "").lower(),
        normalize_phone(lead.get("phone")),
    )


def main():
    if not DIALER_DB_PATH.exists():
        raise SystemExit(f"Dialer DB not found: {DIALER_DB_PATH}")

    leads = json.loads(DIALER_DB_PATH.read_text(encoding="utf-8"))
    if not isinstance(leads, list):
        raise SystemExit("Dialer DB is not a JSON list")

    original_count = len(leads)
    eligible = [lead for lead in leads if is_verified(lead) and not is_suppressed(lead)]
    blocked = [lead for lead in leads if lead not in eligible]

    # Stable per-category promotion: fresh verified records first, then quality.
    categories: dict[str, list[dict]] = {}
    for lead in eligible:
        categories.setdefault(category_key(lead), []).append(lead)

    reordered: list[dict] = []
    category_counts: dict[str, int] = {}
    for category in sorted(categories, key=str.lower):
        rows = sorted(categories[category], key=lead_sort_key)
        category_counts[category] = len(rows)
        reordered.extend(rows)

    # Keep non-callable records at the end, preserving their relative order.
    final = reordered + blocked

    assert len(final) == original_count
    assert len({id(x) for x in final}) == original_count

    DIALER_DB_PATH.write_text(json.dumps(final, indent=2, ensure_ascii=False), encoding="utf-8")

    fresh_count = sum(1 for lead in eligible if freshness_epoch(lead) > 0)
    print("MBM DIALER FRESHNESS PROMOTION")
    print(f"records_before={original_count}")
    print(f"verified_callable={len(eligible)}")
    print(f"blocked_preserved={len(blocked)}")
    print(f"freshness_dated={fresh_count}")
    print(f"categories={len(category_counts)}")
    for category, count in category_counts.items():
        print(f"category={category!r} count={count}")
    print(f"output={DIALER_DB_PATH}")


if __name__ == "__main__":
    main()
