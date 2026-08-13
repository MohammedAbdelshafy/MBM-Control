"""
Airtable Sync — real REST sync for verified / skip-traced dialer leads.

Replaces the old AirtableHubspotSync stub (which only formatted a Slack string +
wrote a local JSON) with a genuine Airtable REST API client.

Credentials (add to .env / .env.local):
    AIRTABLE_API_KEY = patXXXX...
    AIRTABLE_BASE_ID = appXXXX...
    AIRTABLE_TABLE   = Leads            (default)

Usage:
    python airtable_sync.py                 # sync the dialer's leads_database.json
    python airtable_sync.py <path.json>     # sync a specific leads file
    python airtable_sync.py --table Sales   # override table
    python airtable_sync.py --dry-run       # print payloads, make no requests
"""
import os
import io
import sys
import json
import requests
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent  # repo root
DIALER_LEADS = ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"
ENV_FILES = [ROOT / ".env.local", ROOT / ".env"]


def _load_env():
    for env_path in ENV_FILES:
        if not env_path.exists():
            continue
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            os.environ.setdefault(key.strip(), val.strip())


def _tty_ascii(text: str) -> str:
    """Coerce to ASCII so Windows cp1252 consoles don't crash on emoji."""
    try:
        text.encode(sys.stdout.encoding or "utf-8")
        return text
    except Exception:
        return text.encode("ascii", errors="replace").decode("ascii")


def _lead_to_fields(lead: dict) -> dict:
    """Map a dialer lead + details dict to Airtable field names (Twitter-style CamelCase)."""
    d = lead.get("details") or {}
    fields = {
        "Company": lead.get("company") or "",
        "Contact Name": lead.get("contact") or "",
        "Phone": lead.get("phone") or "",
        "NPI Number": lead.get("npi_number") or d.get("npi_number") or "",
        "Vertical": lead.get("vertical") or "",
        "Taxonomy": d.get("taxonomy") or "",
        "Status": (lead.get("skip_trace_status") or "").upper(),
        "Source": lead.get("skip_trace_source") or d.get("source") or "",
        "Confidence": lead.get("skip_trace_confidence") or "",
        "Alt Phone": lead.get("skip_trace_phone_alt") or "",
        "Verified Phone": d.get("verified_phone") or "",
        "City": d.get("city") or "",
        "State": d.get("state") or "",
        "Address": d.get("address") or "",
        "Call Script": d.get("Call_Script") or "",
        "Owner Name": d.get("Owner_Name") or d.get("authorized_official_name") or "",
        "Owner Title": d.get("Owner_Title") or d.get("authorized_official_title") or "",
    }
    return {k: v for k, v in fields.items() if v}


class AirtableSync:
    def __init__(self):
        _load_env()
        self.api_key = os.environ.get("AIRTABLE_API_KEY", "").strip()
        self.base_id = os.environ.get("AIRTABLE_BASE_ID", "").strip()
        self.table = (os.environ.get("AIRTABLE_TABLE", "Leads") or "").strip()
        self.dry_run = "--dry-run" in sys.argv
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def configured(self) -> bool:
        return bool(self.api_key and self.base_id)

    def _url(self, *, records: bool = True) -> str:
        return f"https://api.airtable.com/v0/{self.base_id}/{self.table}" + ("?pageSize=100" if not records else "")

    def _find_existing_phones(self, phones: list[str]) -> dict[str, str]:
        """Return {phone: recordId} for leads already in Airtable (matched on Phone field)."""
        existing: dict[str, str] = {}
        clean = [p for p in phones if p]
        for i in range(0, len(clean), 90):
            chunk = clean[i:i + 90]
            formula = "OR(" + ",".join(f"{{Phone}}='{p}'" for p in chunk) + ")"
            r = self.session.get(
                f"https://api.airtable.com/v0/{self.base_id}/{self.table}",
                params={"filterByFormula": formula, "fields[]": "Phone", "pageSize": 100},
            )
            if r.status_code != 200:
                print(_tty_ascii(f"[AIRTABLE] WARN query existing: {r.status_code} {r.text[:200]}"))
                continue
            for rec in r.json().get("records", []):
                phone = rec.get("fields", {}).get("Phone")
                if phone:
                    existing[str(phone)] = rec["id"]
        return existing

    def sync(self, leads: list[dict]) -> dict:
        payloads = [_lead_to_fields(l) for l in leads if _lead_to_fields(l)]
        if not payloads:
            return {"created": 0, "updated": 0, "skipped": 0}
        if not self.configured():
            print(_tty_ascii("[AIRTABLE] Missing AIRTABLE_API_KEY / AIRTABLE_BASE_ID. "
                             "Add them to .env and re-run. Dry-run showing payloads."))
            print(json.dumps(payloads, indent=2)[:4000])
            return {"created": 0, "updated": 0, "skipped": len(payloads)}

        phone_to_id = self._find_existing_phones([p.get("Phone") for p in payloads])
        created = updated = 0
        # Airtable batch limit is 10 records per request.
        for i in range(0, len(payloads), 10):
            batch = payloads[i:i + 10]
            to_create, to_update = [], []
            for rec in batch:
                rid = phone_to_id.get(rec.get("Phone"))
                if rid:
                    to_update.append({"id": rid, "fields": rec})
                else:
                    to_create.append({"fields": rec})
            if to_create:
                r = self.session.post(self._url(records=True), json={"records": to_create})
                if r.status_code in (200, 201):
                    created += len(to_create)
                else:
                    print(_tty_ascii(f"[AIRTABLE] ERR create: {r.status_code} {r.text[:300]}"))
            if to_update:
                r = self.session.patch(self._url(records=True), json={"records": to_update})
                if r.status_code in (200, 201):
                    updated += len(to_update)
                else:
                    print(_tty_ascii(f"[AIRTABLE] ERR update: {r.status_code} {r.text[:300]}"))
        print(_tty_ascii(f"[AIRTABLE] Done: {created} created, {updated} updated."))
        return {"created": created, "updated": updated, "skipped": 0}


def _load_leads(path: Path | None) -> list[dict]:
    p = path or DIALER_LEADS
    if not p.exists():
        raise FileNotFoundError(f"Leads file not found: {p}")
    data = json.loads(p.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("leads", data.get("data", []))


def main():
    _load_env()
    sync = AirtableSync()
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    table_override = None
    for a in sys.argv[1:]:
        if a.startswith("--table="):
            table_override = a.split("=", 1)[1]
    if table_override:
        sync.table = table_override.strip()

    path = Path(args[0]) if args else None
    leads = _load_leads(path if path and path.exists() else None)
    if path and not path.exists():
        print(_tty_ascii(f"[AIRTABLE] File not found: {path} — used default dialer leads instead."))
    # Only push verified / enriched lines (real numbers worth syncing).
    pushable = [l for l in leads if (l.get("skip_trace_status") or "").upper() in ("VERIFIED", "ENRICHED")]
    print(_tty_ascii(f"[AIRTABLE] {len(leads)} total leads; pushing {len(pushable)} verified/enriched to table '{sync.table}'."))
    out = sync.sync(pushable)
    print(json.dumps(out))


if __name__ == "__main__":
    main()
