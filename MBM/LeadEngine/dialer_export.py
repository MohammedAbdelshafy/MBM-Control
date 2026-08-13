"""
Dialer Export — dump verified / skip-traced leads to CSV (Artifacts) and
optionally push them to Airtable via airtable_sync.

Usage:
    python dialer_export.py                  # CSV only -> MBM/Artifacts/
    python dialer_export.py --airtable        # also sync to Airtable
    python dialer_export.py --all             # include UNVERIFIED too
    python dialer_export.py --out path.csv    # custom output path
"""
import os
import io
import sys
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DIALER_LEADS = ROOT / "mbm-dialer" / "app" / "public" / "leads_database.json"
ARTIFACTS = ROOT / "MBM" / "Artifacts"

FIELD_NAMES = [
    "id", "company", "contact", "vertical", "status",
    "primary_phone", "alt_phone", "npi_number", "taxonomy",
    "source", "confidence", "verified_phone",
    "city", "state", "address", "owner_name", "owner_title", "call_script",
]


def _lead_to_row(lead: dict) -> dict:
    d = lead.get("details") or {}
    return {
        "id": lead.get("id") or "",
        "company": lead.get("company") or "",
        "contact": lead.get("contact") or "",
        "vertical": lead.get("vertical") or "",
        "status": (lead.get("skip_trace_status") or "").upper(),
        "primary_phone": lead.get("phone") or "",
        "alt_phone": lead.get("skip_trace_phone_alt") or "",
        "npi_number": lead.get("npi_number") or d.get("npi_number") or "",
        "taxonomy": d.get("taxonomy") or "",
        "source": lead.get("skip_trace_source") or d.get("source") or "",
        "confidence": lead.get("skip_trace_confidence") or "",
        "verified_phone": d.get("verified_phone") or "",
        "city": d.get("city") or "",
        "state": d.get("state") or "",
        "address": d.get("address") or "",
        "owner_name": d.get("Owner_Name") or d.get("authorized_official_name") or "",
        "owner_title": d.get("Owner_Title") or d.get("authorized_official_title") or "",
        "call_script": d.get("Call_Script") or "",
    }


def load_leads():
    if not DIALER_LEADS.exists():
        raise FileNotFoundError(DIALER_LEADS)
    data = json.loads(DIALER_LEADS.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else data.get("leads", data.get("data", []))


def main():
    out_path = None
    args = sys.argv[1:]
    for i, a in enumerate(args):
        if a.startswith("--out="):
            out_path = Path(a.split("=", 1)[1])
        elif a == "--out" and i + 1 < len(args):
            out_path = Path(args[i + 1])

    leads = load_leads()
    include_all = "--all" in sys.argv
    wanted = leads if include_all else [
        l for l in leads if (l.get("skip_trace_status") or "").upper() in ("VERIFIED", "ENRICHED")
    ]

    if not out_path:
        out_path = ARTIFACTS / "dialer_verified_export.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rows = [_lead_to_row(l) for l in wanted if (l.get("phone") or l.get("skip_trace_phone_alt"))]
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELD_NAMES)
        writer.writeheader()
        writer.writerows(rows)

    print(f"[EXPORT] {len(rows)} rows -> {out_path}")

    if "--airtable" in sys.argv:
        from airtable_sync import AirtableSync, _load_env
        _load_env()
        out = AirtableSync().sync(wanted)
        print(f"[EXPORT] Airtable result: {json.dumps(out)}")


if __name__ == "__main__":
    main()
