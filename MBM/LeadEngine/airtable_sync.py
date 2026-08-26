"""
Airtable Sync — safe operational mirror for verified/enriched Dialer leads.

Airtable is NOT the canonical Dialer source of truth. It is an operational
intelligence/CRM mirror. Canonical dialing eligibility remains controlled by
the LeadEngine verification gates and single-writer paths.

Environment (.env / .env.local):
    AIRTABLE_API_KEY / AIRTABLE_PAT
    AIRTABLE_BASE_ID
    AIRTABLE_TABLE (default: Leads)

Preferred Airtable Leads table: add a stable `Lead ID` field. The sync uses
stable identity first and only falls back to phone for legacy records.
Airtable fields never promote a lead to CALL_READY.
"""
import os
import json
import sys
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
DIALER_LEADS = ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"
ENV_FILES = [ROOT / ".env.local", ROOT / ".env"]


def _load_env() -> None:
    for env_path in ENV_FILES:
        if not env_path.exists():
            continue
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())


def _tty_ascii(text: str) -> str:
    try:
        text.encode(sys.stdout.encoding or "utf-8")
        return text
    except Exception:
        return text.encode("ascii", errors="replace").decode("ascii")


def _stable_lead_id(lead: dict[str, Any]) -> str:
    details = lead.get("details") or {}
    for key in ("lead_id", "id", "npi_number", "npi"):
        value = lead.get(key) or details.get(key)
        if value:
            return str(value).strip()
    return ""


def _lead_to_fields(lead: dict[str, Any]) -> dict[str, Any]:
    details = lead.get("details") or {}
    lead_id = _stable_lead_id(lead)
    fields: dict[str, Any] = {
        "Lead ID": lead_id,
        "Business Name": lead.get("company") or lead.get("business_name") or "",
        "Owner Name": details.get("Owner_Name") or details.get("authorized_official_name") or lead.get("contact") or "",
        "Phone": lead.get("phone") or "",
        "Email": lead.get("email") or "",
        "Industry": lead.get("vertical") or lead.get("segment") or "",
        "Lead Score": lead.get("score") if lead.get("score") is not None else lead.get("priority_score"),
        "Status": (lead.get("skip_trace_status") or lead.get("phone_status") or "").upper(),
        "Source": lead.get("source") or lead.get("skip_trace_source") or details.get("source") or "",
        "Notes": details.get("notes") or lead.get("notes") or "",
        "AI Opportunity": lead.get("ai_opportunity") or lead.get("recommended_offer") or "",
        "Next Best Action": lead.get("next_best_action") or "",
        "AI Service Script": details.get("Call_Script") or lead.get("Call_Script") or "",
        "Lead Stage": lead.get("lead_stage") or lead.get("stage") or "",
        "AI Fit Score": lead.get("ai_fit_score") if lead.get("ai_fit_score") is not None else lead.get("fit_score"),
        "Verified Phone": details.get("verified_phone") or lead.get("verified_phone") or "",
        "Phone Status": lead.get("phone_status") or lead.get("skip_trace_status") or "",
        "Phone Source": lead.get("phone_source") or lead.get("skip_trace_source") or "",
        "Verification Date": lead.get("phone_verified_at") or lead.get("verified_at") or "",
        "Contact Verified": bool(lead.get("contact_identity_verified") or lead.get("owner_verified")),
        "DNC": bool(lead.get("dnc") or lead.get("dnc_status")),
        "Suppressed": bool(lead.get("suppressed") or lead.get("suppression_status")),
        "Segment": lead.get("segment") or lead.get("vertical") or "",
        "Script ID": lead.get("script_id") or "",
        "Sales Strategy": lead.get("sales_strategy") or "",
    }
    return {k: v for k, v in fields.items() if v not in (None, "")}


def _load_leads(path: Path | None) -> list[dict[str, Any]]:
    p = path or DIALER_LEADS
    if not p.exists():
        raise FileNotFoundError(f"Leads file not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("leads", data.get("data", []))


class AirtableSync:
    def __init__(self) -> None:
        _load_env()
        self.api_key = (os.environ.get("AIRTABLE_API_KEY") or os.environ.get("AIRTABLE_PAT") or "").strip()
        self.base_id = os.environ.get("AIRTABLE_BASE_ID", "").strip()
        self.table = (os.environ.get("AIRTABLE_TABLE", "Leads") or "Leads").strip()
        self.dry_run = "--dry-run" in sys.argv
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def configured(self) -> bool:
        return bool(self.api_key and self.base_id)

    def _url(self) -> str:
        return f"https://api.airtable.com/v0/{self.base_id}/{self.table}"

    def _existing_by_identity(self, lead_ids: list[str]) -> dict[str, str]:
        existing: dict[str, str] = {}
        ids = [x.replace("'", "\\'") for x in lead_ids if x]
        for i in range(0, len(ids), 90):
            chunk = ids[i:i + 90]
            formula = "OR(" + ",".join("{Lead ID}='" + value + "'" for value in chunk) + ")"
            try:
                r = self.session.get(
                    self._url(),
                    params={"filterByFormula": formula, "fields[]": "Lead ID", "pageSize": 100},
                    timeout=30,
                )
            except requests.RequestException as exc:
                print(_tty_ascii(f"[AIRTABLE] WARN identity query failed: {exc}"))
                continue
            if r.status_code != 200:
                print(_tty_ascii(f"[AIRTABLE] WARN identity query: {r.status_code} {r.text[:200]}"))
                continue
            for rec in r.json().get("records", []):
                lead_id = rec.get("fields", {}).get("Lead ID")
                if lead_id:
                    existing[str(lead_id)] = rec["id"]
        return existing

    def sync(self, leads: list[dict[str, Any]]) -> dict[str, int]:
        payloads = []
        for lead in leads:
            mapped = _lead_to_fields(lead)
            if mapped.get("Lead ID"):
                payloads.append(mapped)
        if not payloads:
            return {"created": 0, "updated": 0, "skipped": 0}

        if not self.configured() or self.dry_run:
            reason = "dry-run" if self.dry_run else "missing AIRTABLE credentials"
            print(_tty_ascii(f"[AIRTABLE] {reason}; no remote writes performed."))
            return {"created": 0, "updated": 0, "skipped": len(payloads)}

        existing = self._existing_by_identity([p["Lead ID"] for p in payloads])
        created = updated = 0
        for i in range(0, len(payloads), 10):
            batch = payloads[i:i + 10]
            to_create = []
            to_update = []
            for fields in batch:
                rid = existing.get(fields["Lead ID"])
                if rid:
                    to_update.append({"id": rid, "fields": fields})
                else:
                    to_create.append({"fields": fields})
            if to_create:
                try:
                    r = self.session.post(self._url(), json={"records": to_create}, timeout=30)
                    if r.status_code in (200, 201):
                        created += len(to_create)
                    else:
                        print(_tty_ascii(f"[AIRTABLE] ERR create: {r.status_code} {r.text[:300]}"))
                except requests.RequestException as exc:
                    print(_tty_ascii(f"[AIRTABLE] ERR create request: {exc}"))
            if to_update:
                try:
                    r = self.session.patch(self._url(), json={"records": to_update}, timeout=30)
                    if r.status_code in (200, 201):
                        updated += len(to_update)
                    else:
                        print(_tty_ascii(f"[AIRTABLE] ERR update: {r.status_code} {r.text[:300]}"))
                except requests.RequestException as exc:
                    print(_tty_ascii(f"[AIRTABLE] ERR update request: {exc}"))
        print(_tty_ascii(f"[AIRTABLE] Done: {created} created, {updated} updated."))
        return {"created": created, "updated": updated, "skipped": 0}


def main() -> None:
    path_args = [a for a in sys.argv[1:] if not a.startswith("--")]
    table_override = next((a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--table=")), None)
    sync = AirtableSync()
    if table_override:
        sync.table = table_override.strip()
    path = Path(path_args[0]) if path_args else None
    leads = _load_leads(path if path and path.exists() else None)
    pushable = [
        l for l in leads
        if (l.get("skip_trace_status") or l.get("phone_status") or "").upper()
        in ("VERIFIED", "ENRICHED", "VERIFIED_PRIMARY", "VERIFIED_SECONDARY")
    ]
    print(_tty_ascii(f"[AIRTABLE] {len(leads)} total leads; pushing {len(pushable)} verified/enriched to '{sync.table}'."))
    print(json.dumps(sync.sync(pushable)))


if __name__ == "__main__":
    main()
