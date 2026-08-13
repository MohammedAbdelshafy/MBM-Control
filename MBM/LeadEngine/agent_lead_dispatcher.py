"""
MBM Master Agent Lead Dispatcher
================================
Takes all VERIFIED and ENRICHED leads from leads_database.json and feeds them 
directly into ALL active calling, voice, and outreach agents across the system:

Agents & Pipelines Receiving Verified Leads:
  1. Close-Queue Dialer (npi_verified_callsheet.csv -> Twilio Phone Bridge)
  2. Wolf Closer Agent (wolf_closer_agent.py -> High-Ticket AI Closer)
  3. Multi-Touch Cadence Agent (multi_touch_cadence_agent.py -> Multi-Touch Email/SMS Cadence)
  4. Hourly Outreach Agent (hourly_outreach_agent.py -> Automated Email & SMS Outreach)
  5. Ulio.ai Voice Pipeline (ulio_ai_client.py -> Autonomous AI Voice Telephony)
  6. Cold Calling Swarm OS (cold_calling_swarm_os.py -> High-Volume Calling Queue)

Run:
  python MBM/LeadEngine/agent_lead_dispatcher.py
"""

import json
import os
import sys
import io
import csv
import subprocess
from pathlib import Path
from datetime import datetime

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

BASE_DIR = Path(__file__).parent.resolve()
ROOT_DIR = BASE_DIR.parent.parent

DIALER_DB = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"
ARTIFACTS_DIR = ROOT_DIR / "MBM" / "Artifacts"
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

CALLSHEET_CSV = ARTIFACTS_DIR / "npi_verified_callsheet.csv"
COLD_CALLING_QUEUE = BASE_DIR / "cold_calling_queue.json"
CADENCE_QUEUE = BASE_DIR / "multi_touch_queue.json"
ULIO_QUEUE = BASE_DIR / "ulio_voice_queue.json"
LOG_FILE = BASE_DIR / "logs" / "agent_dispatcher.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)


def log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[AGENT DISPATCHER] [{ts}] {msg}"
    print(line)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


# Mutable per-lead state persisted by dialers/progressive cadence INTO the queue
# files. A fresh dispatch must carry these across, or a 15-minute rewrite wipes
# every disposition/stage/last_touch/note the dialers recorded.
MUTABLE_STATE_KEYS = (
    "disposition", "stage", "last_touch", "notes", "called_at", "callback_time",
    "attempts", "priority", "status",
)

# Statuses the dispatcher stamps on fresh rows. Only these are considered
# "un-touched"; anything else from an existing row is real dialer state.
FRESH_STATUS = "QUEUED_FOR_AI_AGENT"


def _load_existing(path: Path) -> list:
    """Read an existing queue file (list shape). Returns [] if missing/broken."""
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict) and "queue" in data:
        q = data["queue"]
        return q if isinstance(q, list) else list(q.values())
    return []


def _lead_key(row: dict) -> str:
    """Stable merge key: phone if present, else id, else company+name."""
    phone = str(row.get("phone") or row.get("verified_phone") or "").strip()
    if phone:
        return f"phone:{phone}"
    lid = row.get("id")
    if lid:
        return f"id:{lid}"
    return f"name:{row.get('name') or row.get('contact') or ''}|{row.get('company') or ''}"


def _merge_queue_state(new_rows: list, path: Path) -> list:
    """
    Merge freshly-qualified rows into the existing queue so dialer state is
    never lost: per-row mutable fields (disposition, stage, last_touch, notes,
    attempts, priority, non-fresh status) are carried over keyed by phone/id.
    New verified leads are added; stale rows no longer qualified are dropped.
    """
    existing = _load_existing(path)
    state_by_key = {}
    for row in existing:
        key = _lead_key(row)
        if key in state_by_key:
            continue
        carried = {}
        for k in MUTABLE_STATE_KEYS:
            if k in row:
                carried[k] = row[k]
        state_by_key[key] = carried

    merged = []
    for row in new_rows:
        out = dict(row)
        key = _lead_key(row)
        carried = state_by_key.get(key, {})
        for k, v in carried.items():
            if k == "status" and v == FRESH_STATUS:
                continue
            out[k] = v
        merged.append(out)
    return merged


def _write_atomic(path: Path, rows: list):
    """Write JSON atomically (temp file + rename) so concurrent dialers never
    read a half-written queue."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, default=str)
    os.replace(tmp, path)


def main():
    log("==========================================================")
    log("  MBM MASTER AGENT LEAD DISPATCHER ACTIVATED")
    log("==========================================================")

    if not DIALER_DB.exists():
        log(f"ERROR: {DIALER_DB} does not exist.")
        return

    with open(DIALER_DB, "r", encoding="utf-8") as f:
        leads = json.load(f)

    # Gate-verify — keeps NPI-registry clinics as well as skip-traced sellers.
    from dialer_verification_gate import check_lead
    qualified = []
    for l in leads:
        res = check_lead(l)
        if res["passed"]:
            l["_gate_source"] = res["verified_source"]
            qualified.append(l)
    log(f"Total Qualified Leads (gate VERIFIED): {len(qualified)} / {len(leads)}")

    if not qualified:
        log("No verified/enriched leads found yet. Waiting for skip tracer to finish more batches...")
        return

    # -------------------------------------------------------------------------
    # 1. Export to NPI Verified Callsheet CSV (For Close-Queue Dialer & Twilio)
    # -------------------------------------------------------------------------
    csv_headers = [
        "npi", "provider_name", "organization_name", "phone", "email",
        "state", "vertical", "skip_trace_status", "confidence", "source",
        "authorized_official_name", "verified_phone"
    ]
    with open(CALLSHEET_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(csv_headers)
        for lead in qualified:
            writer.writerow([
                lead.get("npi_number", "") or (lead.get("details") or {}).get("npi_number", ""),
                lead.get("contact", ""),
                lead.get("company", "") or lead.get("gmaps_name", ""),
                lead.get("phone", ""),
                lead.get("email", "") or lead.get("skip_trace_email", ""),
                lead.get("state", ""),
                lead.get("vertical", "Healthcare/Clinic"),
                lead.get("skip_trace_status", ""),
                lead.get("skip_trace_confidence", "high"),
                (lead.get("skip_trace_source") or ""
                 or (lead.get("details") or {}).get("source") or ""),
                (lead.get("authorized_official_name") or "")
                or (lead.get("details") or {}).get("authorized_official_name", "")
                or lead.get("contact", ""),
                (lead.get("verified_phone") or "")
                or (lead.get("details") or {}).get("verified_phone", "")
            ])
    log(f"✅ Dispatched {len(qualified)} qualified leads to NPI Callsheet CSV: {CALLSHEET_CSV}")

    # -------------------------------------------------------------------------
    # 2. Export to Cold Calling Queue JSON (For Wolf Closer & Cold Calling Swarm OS)
    # -------------------------------------------------------------------------
    swarm_queue = []
    for lead in qualified:
        swarm_queue.append({
            "id": lead.get("id"),
            "name": lead.get("contact"),
            "company": lead.get("company") or lead.get("gmaps_name", ""),
            "phone": lead.get("phone"),
            "alt_phone": lead.get("skip_trace_phone_alt", ""),
            "email": lead.get("email") or lead.get("skip_trace_email", ""),
            "vertical": lead.get("vertical", "Clinic"),
            "skip_trace_status": lead.get("skip_trace_status", ""),
            "verified_source": lead.get("_gate_source", ""),
            "status": "QUEUED_FOR_AI_AGENT",
            "priority": "TIER_A" if lead.get("_gate_source") in (
                "skip_trace_verified", "npi_registry", "npi_callsheet",
                "npi_cold_call_queue") else "TIER_B"
        })
    # MERGE, don't clobber: carry over dialer-persisted state (disposition,
    # stage, last_touch, notes, attempts, priority, status) from the existing
    # queue, and write atomically so concurrent dialers never read partial data.
    cold_merged = _merge_queue_state(swarm_queue, COLD_CALLING_QUEUE)
    _write_atomic(COLD_CALLING_QUEUE, cold_merged)
    log(f"✅ Dispatched {len(cold_merged)} leads to Cold Calling Swarm Queue "
        f"(merged with existing, dialer state preserved): {COLD_CALLING_QUEUE}")

    # -------------------------------------------------------------------------
    # 3. Export to Multi-Touch Cadence Queue JSON (For Multi-Touch & Hourly Outreach)
    # -------------------------------------------------------------------------
    cadence_merged = _merge_queue_state(swarm_queue, CADENCE_QUEUE)
    _write_atomic(CADENCE_QUEUE, cadence_merged)
    log(f"✅ Dispatched {len(cadence_merged)} leads to Multi-Touch Cadence Queue "
        f"(merged with existing): {CADENCE_QUEUE}")

    # -------------------------------------------------------------------------
    # 4. Export to Ulio.ai Voice Queue JSON (For Ulio AI Voice Agent Telephony)
    # -------------------------------------------------------------------------
    ulio_merged = _merge_queue_state(swarm_queue, ULIO_QUEUE)
    _write_atomic(ULIO_QUEUE, ulio_merged)
    log(f"✅ Dispatched {len(ulio_merged)} leads to Ulio.ai Voice Telephony Queue "
        f"(merged with existing): {ULIO_QUEUE}")

    log("==========================================================")
    log(f"  ALL {len(qualified)} QUALIFIED LEADS PASSED TO ALL AGENTS SUCCESSFULLY!")
    log("==========================================================")


if __name__ == "__main__":
    main()
