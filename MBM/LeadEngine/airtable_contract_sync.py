"""Contract-first Airtable sync for the MBM Lead Warehouse.

This module is deliberately separate from the legacy Airtable sync path so it
can be tested and promoted without changing existing production behavior.

Authority model:
- Dialer canonical DB owns identity, phone verification, DNC/suppression and CALL_READY.
- Airtable mirrors structured operational intelligence by stable Lead ID.
- Airtable writes can never promote CALL_READY or overwrite safety fields with guesses.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Iterable

import requests


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BASE = "appJ727ZmeayC9Uk3"
DEFAULT_TABLE = "Leads"
_READ_ONLY_SAFETY_FIELDS = {
    "Verified Phone",
    "Phone Status",
    "Phone Source",
    "Verification Date",
    "Contact Identity Verified",
    "DNC",
    "Suppressed",
}


def _load_env() -> None:
    for path in (ROOT / ".env.local", ROOT / ".env"):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def _lead_id(lead: dict[str, Any]) -> str:
    value = lead.get("lead_id") or lead.get("id") or lead.get("Lead ID")
    if not value:
        raise ValueError("lead is missing stable lead_id")
    return str(value).strip()


def to_airtable_fields(lead: dict[str, Any]) -> dict[str, Any]:
    """Map only safe operational fields; never let Airtable write safety gates."""
    details = lead.get("details") or {}
    fields: dict[str, Any] = {
        "Lead ID": _lead_id(lead),
        "Business Name": lead.get("company") or lead.get("business_name") or "",
        "Owner Name": lead.get("contact") or details.get("Owner_Name") or "",
        "Phone": lead.get("phone") or "",
        "Email": lead.get("email") or "",
        "Industry": lead.get("vertical") or lead.get("industry") or "",
        "Lead Score": lead.get("priority_score") or lead.get("lead_score"),
        "Status": lead.get("status") or lead.get("lead_status") or "",
        "Source": lead.get("source") or details.get("source") or "",
        "Notes": lead.get("notes") or "",
        "AI Opportunity": lead.get("ai_opportunity") or "",
        "Next Best Action": lead.get("next_best_action") or "",
        "AI Service Script": details.get("Call_Script") or lead.get("Call_Script") or "",
        "Lead Stage": lead.get("lead_stage") or "",
        "AI Fit Score": lead.get("ai_fit_score"),
        "Segment": lead.get("segment") or "",
        "Script ID": lead.get("script_id") or "",
        "Sales Strategy": lead.get("sales_strategy") or "",
        "Offer Recommendation": lead.get("offer_recommendation") or "",
    }
    # Safety fields are read-only here. A verified value may be carried for display,
    # but this synchronizer never promotes or changes the canonical decision.
    for field in _READ_ONLY_SAFETY_FIELDS:
        fields.pop(field, None)
    return {key: value for key, value in fields.items() if value not in (None, "", [])}


class AirtableContractSync:
    def __init__(self, *, base_id: str | None = None, table: str = DEFAULT_TABLE) -> None:
        _load_env()
        self.api_key = os.environ.get("AIRTABLE_API_KEY", "").strip()
        self.base_id = (base_id or os.environ.get("AIRTABLE_BASE_ID") or DEFAULT_BASE).strip()
        self.table = table
        if not self.api_key:
            raise RuntimeError("AIRTABLE_API_KEY is required")

        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    @property
    def url(self) -> str:
        return f"https://api.airtable.com/v0/{self.base_id}/{self.table}"

    def _existing_ids(self, lead_ids: Iterable[str]) -> dict[str, str]:
        result: dict[str, str] = {}
        for lead_id in lead_ids:
            formula = "{Lead ID}=" + json.dumps(lead_id)
            response = self.session.get(
                self.url,
                params={"filterByFormula": formula, "pageSize": 10},
                timeout=30,
            )
            response.raise_for_status()
            for record in response.json().get("records", []):
                value = record.get("fields", {}).get("Lead ID")
                if value:
                    result[str(value)] = record["id"]
        return result

    def sync(self, leads: list[dict[str, Any]], *, dry_run: bool = False) -> dict[str, int]:
        mapped = [to_airtable_fields(lead) for lead in leads]
        existing = {} if dry_run else self._existing_ids(field["Lead ID"] for field in mapped)
        created = updated = 0

        for offset in range(0, len(mapped), 10):
            batch = mapped[offset:offset + 10]
            creates: list[dict[str, Any]] = []
            updates: list[dict[str, Any]] = []
            for fields in batch:
                record_id = existing.get(fields["Lead ID"])
                if record_id:
                    updates.append({"id": record_id, "fields": fields})
                else:
                    creates.append({"fields": fields})

            if dry_run:
                created += len(creates)
                updated += len(updates)
                continue

            if creates:
                response = self.session.post(self.url, json={"records": creates}, timeout=30)
                response.raise_for_status()
                created += len(creates)
            if updates:
                response = self.session.patch(self.url, json={"records": updates}, timeout=30)
                response.raise_for_status()
                updated += len(updates)

        return {"created": created, "updated": updated, "total": len(mapped)}


__all__ = ["AirtableContractSync", "to_airtable_fields"]
