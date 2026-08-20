#!/usr/bin/env python3
"""
MBM Dialer — Daily Refresh + Bad-Number Cleanup
================================================
The single daily orchestrator that keeps the dialer fresh, clean, and
call-ready. Every run:

  1. READ dialer feedback (dispositions + founder comments)
  2. UPDATE canonical leads with structured feedback
  3. INVALIDATE bad phones (permanent suppression)
  4. REMOVE DNC records from active queue
  5. DEDUPLICATE the active queue
  6. ARCHIVE stale active leads (per existing retention rules)
  7. SCORE and SORT with fresh leads rising to the top
  8. SYNC the dialer database through the single-writer gateway
  9. REPORT daily dialer health + today's job

Reads:
  - mbm-dialer/app/public/leads_database.json  (canonical DB)
  - MBM/LeadEngine/logs/close_dispositions.json (Twilio bridge dispositions)
  - MBM/LeadEngine/logs/call_dispositions.json  (Express API dispositions)
  - MBM/LeadEngine/dialer_comments.json         (founder comments/decisions)
  - MBM/Artifacts/suppressed_bad_phones.json     (permanent suppression index)
  - MBM/Artifacts/quarantined_bad_leads.json     (quarantine history)

Writes:
  - mbm-dialer/app/public/leads_database.json   (rebuilt, reordered)
  - MBM/Artifacts/suppressed_bad_phones.json    (updated suppression index)
  - MBM/Artifacts/quarantined_bad_leads.json    (updated quarantine)
  - MBM/Artifacts/daily_refresh_report.json     (machine-readable report)
  - MBM/Artifacts/daily_refresh_report.md       (human-readable report)

Usage:
  python MBM/LeadEngine/daily_refresh.py              # full refresh
  python MBM/LeadEngine/daily_refresh.py --dry-run    # report only
  python MBM/LeadEngine/daily_refresh.py --audit      # audit current DB
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

sys.stdout.reconfigure(encoding="utf-8")

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.dialer_queue_engine import (
    assign_lead_metadata,
    audit_counts,
    build_global_queue,
    get_callable_state,
    ordered_db_records,
    print_audit,
    rank_main_queue,
    top_25_audit,
    load_suppression_index,
    _norm_phone,
    _parse_ts,
    HARD_SUPPRESSION_DISPOSITIONS,
)
from MBM.LeadEngine.dialer_gateway import commit_dialer_db
from MBM.LeadEngine.rebuild_dialer_queue import (
    load_quarantined_history,
    load_suppressed_phone_records,
)

# ── Paths ──────────────────────────────────────────────────────────────────
DIALER_DB = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"
CLOSE_DISPOSITIONS = ROOT_DIR / "MBM" / "LeadEngine" / "logs" / "close_dispositions.json"
CALL_DISPOSITIONS = ROOT_DIR / "MBM" / "LeadEngine" / "logs" / "call_dispositions.json"
COMMENTS_FILE = ROOT_DIR / "MBM" / "LeadEngine" / "dialer_comments.json"
SUPPRESSION_FILE = ROOT_DIR / "MBM" / "Artifacts" / "suppressed_bad_phones.json"
QUARANTINE_FILE = ROOT_DIR / "MBM" / "Artifacts" / "quarantined_bad_leads.json"
REPORT_JSON = ROOT_DIR / "MBM" / "Artifacts" / "daily_refresh_report.json"
REPORT_MD = ROOT_DIR / "MBM" / "Artifacts" / "daily_refresh_report.md"

# ── Feedback Signal Detection ──────────────────────────────────────────────

# Patterns that indicate a bad/dead/invalid phone number (fuzzy-tolerant).
BAD_NUMBER_PATTERNS: List[re.Pattern] = [
    re.compile(r"bad\s*number", re.I),
    re.compile(r"wrong\s*number", re.I),
    re.compile(r"invalid\s*number", re.I),
    re.compile(r"dead\s*number", re.I),
    re.compile(r"disconnected", re.I),
    re.compile(r"not\s*working", re.I),
    re.compile(r"doesn[t'+]?t\s*work", re.I),
    re.compile(r"no\s*longer\s*in\s*service", re.I),
    re.compile(r"out\s*of\s*service", re.I),
    re.compile(r"number\s*not\s*in\s*service", re.I),
    re.compile(r"wrong\s*person", re.I),
    re.compile(r"not\s*(the\s*)?(right|correct)\s*person", re.I),
    re.compile(r"non[\s-]*owner", re.I),
    re.compile(r"not\s*the\s*owner", re.I),
    re.compile(r"tenant", re.I),
    re.compile(r"relative", re.I),
    re.compile(r"associate", re.I),
]

# Patterns that indicate DNC (Do Not Call).
DNC_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bdnc\b", re.I),
    re.compile(r"do\s*not\s*call", re.I),
    re.compile(r"don'?t\s*call", re.I),
    re.compile(r"never\s*call", re.I),
    re.compile(r"stop\s*calling", re.I),
    re.compile(r"remove\s*me", re.I),
    re.compile(r"opt\s*out", re.I),
    re.compile(r"unsubscribe", re.I),
    re.compile(r"take\s*me\s*off", re.I),
]

# Patterns that indicate a callback is needed.
CALLBACK_PATTERNS: List[re.Pattern] = [
    re.compile(r"call\s*back", re.I),
    re.compile(r"follow\s*up", re.I),
    re.compile(r"try\s*again", re.I),
    re.compile(r"tomorrow", re.I),
    re.compile(r"next\s*week", re.I),
    re.compile(r"later", re.I),
    re.compile(r"scheduled", re.I),
    re.compile(r"appointment", re.I),
]

# Patterns for hot/interested leads.
HOT_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bhot\b", re.I),
    re.compile(r"interested", re.I),
    re.compile(r"looks?\s*good", re.I),
    re.compile(r"send\s*(me\s*)?(the\s*)?(info|details|offer|proposal)", re.I),
    re.compile(r"let\s*s\s*(do\s*it|proceed|move\s*forward)", re.I),
    re.compile(r"sounds?\s*great", re.I),
    re.compile(r"let\s*s\s*talk", re.I),
]

# Patterns for negative outcomes.
NOT_INTERESTED_PATTERNS: List[re.Pattern] = [
    re.compile(r"not\s*interested", re.I),
    re.compile(r"no\s*thanks?", re.I),
    re.compile(r"not\s*now", re.I),
    re.compile(r"already\s*(sold|have|using)", re.I),
    re.compile(r"sold", re.I),
]

# Patterns for sold property.
SOLD_PATTERNS: List[re.Pattern] = [
    re.compile(r"\bsold\b", re.I),
    re.compile(r"already\s*sold", re.I),
    re.compile(r"closed", re.I),
    re.compile(r"under\s*contract", re.I),
]


def classify_comment(text: str) -> Dict[str, Any]:
    """Classify a free-text comment into structured signals.

    Returns a dict with flags and the matched classification:
      { "bad_number": bool, "dnc": bool, "callback": bool,
        "hot": bool, "not_interested": bool, "sold": bool,
        "wrong_person": bool, "classification": str, "raw": str }
    """
    if not text:
        return {"classification": "NONE", "raw": ""}

    result: Dict[str, Any] = {
        "bad_number": False,
        "dnc": False,
        "callback": False,
        "hot": False,
        "not_interested": False,
        "sold": False,
        "wrong_person": False,
        "classification": "NONE",
        "raw": text,
    }

    for pat in BAD_NUMBER_PATTERNS:
        if pat.search(text):
            result["bad_number"] = True
            break

    for pat in DNC_PATTERNS:
        if pat.search(text):
            result["dnc"] = True
            break

    for pat in CALLBACK_PATTERNS:
        if pat.search(text):
            result["callback"] = True
            break

    for pat in HOT_PATTERNS:
        if pat.search(text):
            result["hot"] = True
            break

    for pat in NOT_INTERESTED_PATTERNS:
        if pat.search(text):
            result["not_interested"] = True
            break

    for pat in SOLD_PATTERNS:
        if pat.search(text):
            result["sold"] = True
            break

    for pat in BAD_NUMBER_PATTERNS:
        if pat.search(text) and "wrong person" in text.lower():
            result["wrong_person"] = True
            break
    if re.search(r"wrong\s*person", text, re.I):
        result["wrong_person"] = True

    # Determine primary classification (most severe wins)
    if result["dnc"]:
        result["classification"] = "DNC"
    elif result["wrong_person"]:
        result["classification"] = "WRONG_PERSON"
    elif result["bad_number"]:
        result["classification"] = "BAD_NUMBER"
    elif result["sold"]:
        result["classification"] = "SOLD"
    elif result["not_interested"]:
        result["classification"] = "NOT_INTERESTED"
    elif result["hot"]:
        result["classification"] = "HOT"
    elif result["callback"]:
        result["classification"] = "CALLBACK"

    return result


# ── Data Loading ───────────────────────────────────────────────────────────

def _load_json(path: Path) -> Any:
    if not path.exists():
        return [] if path.suffix == ".json" else {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return [] if path.suffix == ".json" else {}


def _load_leads() -> List[Dict[str, Any]]:
    data = _load_json(DIALER_DB)
    if isinstance(data, list):
        return data
    return data.get("leads", [])


def _load_close_dispositions() -> List[Dict[str, Any]]:
    """Load Twilio bridge dispositions from close_queue_dialer.py."""
    data = _load_json(CLOSE_DISPOSITIONS)
    return data if isinstance(data, list) else []


def _load_call_dispositions() -> List[Dict[str, Any]]:
    """Load Express API dispositions from server/index.js."""
    data = _load_json(CALL_DISPOSITIONS)
    return data if isinstance(data, list) else []


def _load_founder_comments() -> List[Dict[str, Any]]:
    """Load founder comments/decisions from dialer_comments.json."""
    data = _load_json(COMMENTS_FILE)
    return data if isinstance(data, list) else []


# ── Core Processing ────────────────────────────────────────────────────────

def _find_lead_by_id(leads: List[Dict[str, Any]], lead_id: str) -> Optional[Dict[str, Any]]:
    for lead in leads:
        if str(lead.get("id")) == str(lead_id):
            return lead
    return None


def _find_lead_by_phone(leads: List[Dict[str, Any]], phone: str) -> Optional[Dict[str, Any]]:
    norm = _norm_phone(phone)
    if not norm:
        return None
    for lead in leads:
        if _norm_phone(lead.get("phone") or "") == norm:
            return lead
    return None


def process_dispositions(
    leads: List[Dict[str, Any]],
    close_disps: List[Dict[str, Any]],
    call_disps: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Process call disposition logs and update lead records.

    Returns stats about what was processed.
    """
    stats = {
        "dispositions_processed": 0,
        "bad_numbers_detected": 0,
        "dnc_detected": 0,
        "leads_updated": 0,
    }

    # Merge both disposition sources
    all_disps = []
    for d in close_disps:
        all_disps.append({
            "lead_id": d.get("lead_id") or d.get("id"),
            "phone": d.get("phone"),
            "outcome": (d.get("outcome") or d.get("disposition") or "").lower(),
            "detail": d.get("detail") or d.get("notes") or "",
            "timestamp": d.get("timestamp"),
            "source": "close_queue_dialer",
        })
    for d in call_disps:
        all_disps.append({
            "lead_id": d.get("lead_id") or d.get("id"),
            "phone": d.get("phone"),
            "outcome": (d.get("outcome") or d.get("disposition") or "").lower(),
            "detail": d.get("detail") or d.get("notes") or "",
            "timestamp": d.get("timestamp"),
            "source": "express_api",
        })

    for disp in all_disps:
        stats["dispositions_processed"] += 1
        outcome = disp["outcome"]

        # Find the lead
        lead = None
        if disp.get("lead_id"):
            lead = _find_lead_by_id(leads, disp["lead_id"])
        if not lead and disp.get("phone"):
            lead = _find_lead_by_phone(leads, disp["phone"])
        if not lead:
            continue

        # Update lead state
        now = datetime.now(timezone.utc).isoformat()
        lead["last_disposition"] = outcome
        lead["last_disposition_at"] = disp.get("timestamp") or now
        lead["last_touch"] = disp.get("timestamp") or now
        lead["attempts"] = int(lead.get("attempts") or 0) + 1

        if not lead.get("disposition"):
            lead["disposition"] = outcome
        if not lead.get("outcome"):
            lead["outcome"] = outcome

        # Process outcome
        if outcome in ("bad-number", "bad_number", "wrong-number", "wrong_number"):
            stats["bad_numbers_detected"] += 1
            phone = _norm_phone(lead.get("phone") or "")
            if phone:
                _add_to_suppression(phone, f"disposition:{outcome}", lead.get("id"))
            lead["disposition"] = "BAD_NUMBER"
            lead["outcome"] = "BAD_NUMBER"
            lead["suppression_reason"] = "BAD_NUMBER"
            lead["callable"] = False

        elif "dnc" in outcome or "do_not_call" in outcome or "do-not-call" in outcome:
            stats["dnc_detected"] += 1
            lead["disposition"] = "DNC"
            lead["outcome"] = "DNC"
            lead["suppression_reason"] = "DNC"
            lead["callable"] = False

        elif outcome in ("answered", "voicemail", "no-answer", "no_answer", "busy"):
            # Mark as contacted but not suppressed
            pass

        stats["leads_updated"] += 1

    return stats


def process_founder_comments(
    leads: List[Dict[str, Any]],
    comments: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Process founder comments/decisions and update lead records.

    Returns stats about what was processed.
    """
    stats = {
        "comments_processed": 0,
        "bad_numbers_detected": 0,
        "dnc_detected": 0,
        "callbacks_scheduled": 0,
        "hot_leads_found": 0,
        "leads_updated": 0,
    }

    for comment in comments:
        stats["comments_processed"] += 1
        lead_id = comment.get("lead_id") or comment.get("id")
        status = (comment.get("status") or comment.get("decision_label") or comment.get("decision_id") or "").strip()
        note = (comment.get("note") or comment.get("notes") or "").strip()
        combined_text = f"{status} {note}".strip()

        # Classify the combined status + note
        classification = classify_comment(combined_text)

        # Find the lead
        lead = None
        if lead_id:
            lead = _find_lead_by_id(leads, lead_id)
        if not lead and comment.get("phone"):
            lead = _find_lead_by_phone(leads, comment["phone"])
        if not lead:
            continue

        now = datetime.now(timezone.utc).isoformat()
        lead["last_comment"] = combined_text
        lead["last_comment_at"] = comment.get("recorded_at") or comment.get("at") or now
        lead["last_touch"] = lead["last_comment_at"]
        lead["attempts"] = int(lead.get("attempts") or 0) + 1

        # Apply classification
        if classification["bad_number"] or classification["wrong_person"]:
            stats["bad_numbers_detected"] += 1
            phone = _norm_phone(lead.get("phone") or "")
            if phone:
                _add_to_suppression(phone, f"comment:{classification['classification']}", lead.get("id"))
            lead["disposition"] = classification["classification"]
            lead["outcome"] = classification["classification"]
            lead["suppression_reason"] = classification["classification"]
            lead["callable"] = False

        elif classification["dnc"]:
            stats["dnc_detected"] += 1
            phone = _norm_phone(lead.get("phone") or "")
            if phone:
                _add_to_suppression(phone, "comment:DNC", lead.get("id"))
            lead["disposition"] = "DNC"
            lead["outcome"] = "DNC"
            lead["suppression_reason"] = "DNC"
            lead["callable"] = False

        elif classification["callback"]:
            stats["callbacks_scheduled"] += 1
            lead["disposition"] = "CALL_BACK"
            lead["outcome"] = "CALL_BACK"
            lead["follow_up_requested"] = True
            lead["follow_up_at"] = now

        elif classification["hot"]:
            stats["hot_leads_found"] += 1
            lead["disposition"] = "HOT"
            lead["outcome"] = "HOT"
            # Boost intent/motivation scores
            for field in ("intent_score", "motivation_score", "deal_score"):
                current = int(lead.get(field) or 0)
                if current < 90:
                    lead[field] = 90
            lead["callability_score"] = 95

        elif classification["not_interested"]:
            lead["disposition"] = "NOT_INTERESTED"
            lead["outcome"] = "NOT_INTERESTED"
            # Not suppressed — just not priority
            lead["callability_score"] = min(int(lead.get("callability_score") or 50), 30)

        elif classification["sold"]:
            lead["disposition"] = "SOLD"
            lead["outcome"] = "SOLD"
            lead["suppression_reason"] = "SOLD"
            lead["callable"] = False

        elif status.upper() in ("SELLER WARMED", "AI BUYER WARMED", "QUALIFIED OPPORTUNITY"):
            lead["disposition"] = status.upper().replace(" ", "_")
            lead["outcome"] = status.upper().replace(" ", "_")
            # Boost scores for warmed leads
            for field in ("intent_score", "motivation_score"):
                current = int(lead.get(field) or 0)
                if current < 85:
                    lead[field] = 85
            lead["callability_score"] = 90

        elif status.upper() in ("MEETING BOOKED", "PROPOSAL SENT", "DEAL WON", "CASH OFFER MADE"):
            lead["disposition"] = status.upper().replace(" ", "_")
            lead["outcome"] = status.upper().replace(" ", "_")
            lead["last_outcome"] = status.upper().replace(" ", "_")

        stats["leads_updated"] += 1

    return stats


# ── Suppression Management ─────────────────────────────────────────────────

_suppressed_phones: Optional[Set[str]] = None
_suppression_log: List[Dict[str, Any]] = []


def _load_current_suppression() -> Set[str]:
    global _suppressed_phones
    if _suppressed_phones is None:
        _suppressed_phones = load_suppression_index()
    return _suppressed_phones


def _add_to_suppression(phone_digits: str, reason: str, lead_id: str = "") -> None:
    """Add a phone to the permanent suppression index."""
    global _suppressed_phones
    current = _load_current_suppression()
    if phone_digits not in current:
        current.add(phone_digits)
        _suppression_log.append({
            "phone": f"+1{phone_digits}" if len(phone_digits) == 10 else phone_digits,
            "reason": reason,
            "lead_id": lead_id,
            "suppressed_at": datetime.now(timezone.utc).isoformat(),
        })


def _save_suppression_index() -> int:
    """Persist the suppression index and return the count of suppressed phones."""
    global _suppressed_phones
    current = _load_current_suppression()

    # Load existing file to preserve existing entries
    existing: Set[str] = set()
    if SUPPRESSION_FILE.exists():
        try:
            data = json.loads(SUPPRESSION_FILE.read_text(encoding="utf-8"))
            for p in data.get("suppressed_phones", []):
                existing.add(_norm_phone(str(p)))
        except Exception:
            pass

    # Merge
    all_phones = existing | current

    # Format as E.164
    formatted = sorted(
        f"+1{p}" if len(p) == 10 else p
        for p in all_phones if p
    )

    payload = {
        "total_suppressed_phones": len(formatted),
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "suppressed_phones": formatted,
        "recent_additions": _suppression_log[-50:] if _suppression_log else [],
    }

    SUPPRESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    SUPPRESSION_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return len(formatted)


def _save_quarantine(leads: List[Dict[str, Any]]) -> int:
    """Add newly quarantined leads to the quarantine file."""
    existing: List[Dict[str, Any]] = []
    if QUARANTINE_FILE.exists():
        try:
            data = json.loads(QUARANTINE_FILE.read_text(encoding="utf-8"))
            existing = data.get("quarantined_leads", [])
        except Exception:
            pass

    existing_ids = {str(l.get("id")) for l in existing}
    added = 0
    now = datetime.now(timezone.utc).isoformat()

    for lead in leads:
        state = get_callable_state(lead)
        bucket = state["queue_bucket"]
        if bucket not in ("SUPPRESSED", "QUARANTINED"):
            continue
        lead_id = str(lead.get("id"))
        if lead_id in existing_ids:
            continue

        # Create quarantine record preserving full history
        record = dict(lead)
        record["quarantined"] = True
        record["quarantined_at"] = now
        record["quarantine_reason"] = state.get("suppression_reason") or state.get("blocked_reason") or bucket
        record["history_source"] = "daily_refresh"
        existing.append(record)
        existing_ids.add(lead_id)
        added += 1

    QUARANTINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "total_quarantined": len(existing),
        "last_updated": now,
        "quarantined_leads": existing,
    }
    QUARANTINE_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return added


# ── Deduplication ──────────────────────────────────────────────────────────

def deduplicate_active_queue(leads: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
    """Remove duplicate leads from the active callable queue.

    Preserves the record with the highest priority_score for each unique phone.
    Non-callable records are always preserved (they are history).
    """
    phone_to_best: Dict[str, Dict[str, Any]] = {}
    non_callable: List[Dict[str, Any]] = []
    seen_ids: Set[str] = set()
    duplicates_removed = 0

    for lead in leads:
        lead_id = str(lead.get("id"))
        state = get_callable_state(lead)

        if not state["main_queue"]:
            # Non-callable records: always preserve
            non_callable.append(lead)
            continue

        phone = _norm_phone(lead.get("phone") or "")
        if not phone:
            non_callable.append(lead)
            continue

        prio = int(lead.get("priority_score") or 0)
        if phone in phone_to_best:
            existing_prio = int(phone_to_best[phone].get("priority_score") or 0)
            if prio > existing_prio:
                # This lead is better — demote the old one
                old = phone_to_best[phone]
                old["_callable_state"] = {"queue_bucket": "ALREADY_CONTACTED", "callable": False, "main_queue": False}
                non_callable.append(old)
                phone_to_best[phone] = lead
            else:
                # This lead is a duplicate — demote it
                lead["_callable_state"] = {"queue_bucket": "ALREADY_CONTACTED", "callable": False, "main_queue": False}
                non_callable.append(lead)
            duplicates_removed += 1
        else:
            phone_to_best[phone] = lead

    deduped = list(phone_to_best.values())
    return deduped + non_callable, duplicates_removed


# ── Stale Lead Archival ────────────────────────────────────────────────────

def archive_stale_leads(
    leads: List[Dict[str, Any]],
    days_stale: int = 30,
) -> Tuple[List[Dict[str, Any]], int]:
    """Archive leads that are old, uncalled, and have no recent signal.

    A lead is archived (removed from active queue) when:
    - It's in the main queue (callable + uncalled + verified)
    - It has no recent activity (no comment, no outcome, no enrichment)
    - Its newest timestamp is older than `days_stale` days
    - It has a low or declining freshness score

    Leads with founder comments or recent outcomes are NEVER archived.
    """
    now = datetime.now(timezone.utc)
    archived = 0
    results: List[Dict[str, Any]] = []

    for lead in leads:
        state = get_callable_state(lead)

        # Only consider callable leads in the main queue
        if not state["main_queue"]:
            results.append(lead)
            continue

        # Never archive if there's a recent comment/outcome
        if lead.get("last_comment") or lead.get("last_comment_at"):
            results.append(lead)
            continue
        if lead.get("disposition") and lead["disposition"] not in ("", "NONE", "null"):
            results.append(lead)
            continue
        if lead.get("outcome") and lead["outcome"] not in ("", "NONE", "null"):
            results.append(lead)
            continue

        # Check freshness stage
        stage = state["freshness_stage"]
        if stage in ("NEWLY_IMPORTED", "NEWLY_VERIFIED", "NEWLY_ENRICHED"):
            # Fresh leads are never stale
            results.append(lead)
            continue

        # Check if oldest possible activity is too old
        newest_epoch = state.get("newest_timestamp_epoch") or 0
        if newest_epoch > 0:
            newest_dt = datetime.fromtimestamp(newest_epoch, tz=timezone.utc)
            age_days = (now - newest_dt).days
            if age_days < days_stale:
                results.append(lead)
                continue

        # Archive this lead
        lead["queue_bucket"] = "ALREADY_CONTACTED"
        lead["callable"] = False
        lead["main_queue"] = False
        lead["suppression_reason"] = lead.get("suppression_reason") or f"STALE_ARCHIVED_{days_stale}D"
        archived += 1
        results.append(lead)

    return results, archived


# ── Main Orchestrator ──────────────────────────────────────────────────────

def run_daily_refresh(dry_run: bool = False, quiet: bool = False) -> Dict[str, Any]:
    """Execute the full daily refresh pipeline."""
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()

    if not quiet:
        print("=" * 75)
        print("  MBM DIALER DAILY REFRESH + BAD-NUMBER CLEANUP")
        print(f"  {now_iso}")
        print("=" * 75)

    # ── Step 0: Load current state ──────────────────────────────────────
    if not DIALER_DB.exists():
        raise SystemExit(f"Dialer DB not found: {DIALER_DB}")

    leads = _load_leads()
    pre_count = len(leads)
    if not quiet:
        print(f"\n  [0] Loaded {pre_count} leads from dialer database.")

    # Load all feedback sources
    close_disps = _load_close_dispositions()
    call_disps = _load_call_dispositions()
    founder_comments = _load_founder_comments()
    if not quiet:
        print(f"  [0] Loaded {len(close_disps)} close dispositions, {len(call_disps)} call dispositions, {len(founder_comments)} founder comments.")

    # Load suppression index
    _load_current_suppression()

    # ── Step 1: Process dispositions ────────────────────────────────────
    disp_stats = process_dispositions(leads, close_disps, call_disps)
    if not quiet:
        print(f"\n  [1] Dispositions processed: {disp_stats['dispositions_processed']}")
        print(f"      Bad numbers detected: {disp_stats['bad_numbers_detected']}")
        print(f"      DNC detected: {disp_stats['dnc_detected']}")
        print(f"      Leads updated: {disp_stats['leads_updated']}")

    # ── Step 2: Process founder comments ────────────────────────────────
    comment_stats = process_founder_comments(leads, founder_comments)
    if not quiet:
        print(f"\n  [2] Founder comments processed: {comment_stats['comments_processed']}")
        print(f"      Bad numbers detected: {comment_stats['bad_numbers_detected']}")
        print(f"      DNC detected: {comment_stats['dnc_detected']}")
        print(f"      Callbacks scheduled: {comment_stats['callbacks_scheduled']}")
        print(f"      Hot leads found: {comment_stats['hot_leads_found']}")
        print(f"      Leads updated: {comment_stats['leads_updated']}")

    # ── Step 3: Suppress bad phones permanently ─────────────────────────
    # Scan for any leads that now have bad_number/dnc dispositions
    # and ensure their phones are in the suppression index.
    newly_suppressed = 0
    for lead in leads:
        phone = _norm_phone(lead.get("phone") or "")
        if not phone:
            continue
        disp = (lead.get("disposition") or "").upper()
        reason = (lead.get("suppression_reason") or "").upper()
        if disp in ("BAD_NUMBER", "WRONG_NUMBER", "WRONG_PERSON", "DNC", "DO_NOT_CALL", "SOLD") or \
           "BAD_NUMBER" in reason or "DNC" in reason:
            if phone not in _load_current_suppression():
                _add_to_suppression(phone, f"daily_refresh:{disp or reason}", lead.get("id"))
                newly_suppressed += 1

    if not quiet:
        print(f"\n  [3] Newly suppressed phones: {newly_suppressed}")
        print(f"      Total suppression index: {len(_load_current_suppression())}")

    # ── Step 4: Deduplication ───────────────────────────────────────────
    leads, dups_removed = deduplicate_active_queue(leads)
    if not quiet:
        print(f"\n  [4] Duplicates removed from active queue: {dups_removed}")

    # ── Step 5: Archive stale leads ─────────────────────────────────────
    leads, archived = archive_stale_leads(leads, days_stale=30)
    if not quiet:
        print(f"\n  [5] Stale leads archived (30+ days, no signal): {archived}")

    # ── Step 6: Rebuild queue (fresh leads rise) ────────────────────────
    if not quiet:
        print(f"\n  [6] Rebuilding queue — fresh leads rising to the top...")

    # Merge quarantined history back in
    by_id = {str(l.get("id")): l for l in leads}
    for rec in load_quarantined_history(QUARANTINE_FILE):
        if str(rec.get("id")) not in by_id:
            leads.append(rec)
            by_id[str(rec.get("id"))] = rec

    # Enrich 100% of leads with segment-aware dialogue playbooks & script_id
    from MBM.LeadEngine.dialer_script_engine import enrich_leads_with_playbooks
    leads = enrich_leads_with_playbooks(leads)

    # Build canonical queue
    buckets = build_global_queue(leads, call_now_size=25, next_size=75)
    ordered = ordered_db_records(buckets)

    # ── Step 7: Verify top-of-dialer ordering ──────────────────────────
    top25 = [l for l in ordered if l.get("main_queue")][:25]
    t25_audit = top_25_audit(top25)
    counts = audit_counts(ordered)

    if not quiet:
        print_audit(ordered, "DAILY REFRESH RESULT")

    # ── Step 8: Save quarantine + suppression ───────────────────────────
    if not dry_run:
        new_suppressed = _save_suppression_index()
        new_quarantined = _save_quarantine(leads)
        if not quiet:
            print(f"\n  [8] Suppression index saved: {new_suppressed} total")
            print(f"      Quarantine updated: +{new_quarantined} new records")

    # ── Step 9: Commit to dialer DB ─────────────────────────────────────
    commit_result = {}
    if not dry_run:
        for lead in ordered:
            lead.pop("_callable_state", None)

        commit_result = commit_dialer_db(
            ordered,
            reason="daily_refresh",
            allow_shrink=True,
            author="DAILY_REFRESH",
        )
        if not quiet:
            print(f"\n  [9] Committed {commit_result.get('final_count', len(ordered))} records to dialer DB.")
            print(f"      Rejected synthetic: {commit_result.get('rejected_synthetic', 0)}")
            print(f"      Rejected suppressed: {commit_result.get('rejected_suppressed', 0)}")
            print(f"      Rejected bad phone: {commit_result.get('rejected_bad_phone', 0)}")

    # ── Step 10: Verify actual dialer ordering ──────────────────────────
    if not dry_run and DIALER_DB.exists():
        actual_db = _load_leads()
        actual_top = actual_db[:10]
        if not quiet:
            print(f"\n  [10] TOP 10 OF ACTUAL DIALER DB (verification):")
            for i, lead in enumerate(actual_top[:10], 1):
                phone = lead.get("phone", "")
                disp = lead.get("disposition", "")
                callable_flag = lead.get("callable", True)
                bucket = lead.get("queue_bucket", "")
                print(f"       #{i:02d} | {phone:<14} | {lead.get('contact', '')[:24]:<24} | disp={disp:<14} | callable={callable_flag} | bucket={bucket}")

    # ── Step 11: Generate health report ─────────────────────────────────
    fresh_callable = counts.get("FRESH_CALL_NOW", 0) + counts.get("FRESH_NEXT", 0)
    new_leads = counts.get("NEW_VERIFIED", 0)

    # Find top 10 leads
    top10 = []
    for lead in ordered[:10]:
        top10.append({
            "rank": lead.get("priority_rank", 0),
            "id": lead.get("id"),
            "company": (lead.get("company") or "")[:40],
            "contact": (lead.get("contact") or "")[:30],
            "phone": lead.get("phone"),
            "vertical": (lead.get("vertical") or "")[:24],
            "priority_score": lead.get("priority_score"),
            "freshness_score": lead.get("freshness_score"),
            "freshness_label": lead.get("freshness_label", ""),
            "queue_bucket": lead.get("queue_bucket"),
        })

    report = {
        "status": "dry_run" if dry_run else "success",
        "timestamp": now_iso,
        "pre_refresh_count": pre_count,
        "post_refresh_count": counts.get("TOTAL", 0),
        "metrics": {
            "new_leads": new_leads,
            "fresh_callable_leads": fresh_callable,
            "leads_promoted": 0,  # computed below
            "leads_archived": archived,
            "duplicates_removed": dups_removed,
            "bad_numbers_detected": disp_stats["bad_numbers_detected"] + comment_stats["bad_numbers_detected"],
            "bad_numbers_suppressed": newly_suppressed,
            "dnc_suppressed": disp_stats["dnc_detected"] + comment_stats["dnc_detected"],
            "replacement_phones_found": 0,
            "founder_comments_processed": comment_stats["comments_processed"],
            "callbacks_scheduled": comment_stats["callbacks_scheduled"],
        },
        "queue_counts": {
            "TOTAL": counts.get("TOTAL", 0),
            "MAIN_QUEUE": counts.get("MAIN_QUEUE", 0),
            "FRESH_CALL_NOW": counts.get("FRESH_CALL_NOW", 0),
            "FRESH_NEXT": counts.get("FRESH_NEXT", 0),
            "UNCALLED_VERIFIED": counts.get("UNCALLED_VERIFIED", 0),
            "ALREADY_CONTACTED": counts.get("ALREADY_CONTACTED", 0),
            "VERIFICATION_REQUIRED": counts.get("VERIFICATION_REQUIRED", 0),
            "SUPPRESSED": counts.get("SUPPRESSED", 0),
            "QUARANTINED": counts.get("QUARANTINED", 0),
        },
        "top_10": top10,
        "top25_gate_pass": t25_audit["pass"],
        "commit": {
            "ok": commit_result.get("ok"),
            "final_count": commit_result.get("final_count"),
        },
    }

    # Save report
    REPORT_JSON.parent.mkdir(parents=True, exist_ok=True)
    REPORT_JSON.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    # Generate human-readable report
    _generate_report_md(report, top10, counts)

    if not quiet:
        print(f"\n  [11] Daily report saved to: {REPORT_JSON.name}")
        _print_todays_job(report)

    return report


def _generate_report_md(
    report: Dict[str, Any],
    top10: List[Dict[str, Any]],
    counts: Dict[str, int],
) -> None:
    """Generate the human-readable daily dialer health report."""
    m = report["metrics"]
    lines = [
        "# MBM DIALER DAILY HEALTH REPORT",
        "",
        f"**Date**: {report['timestamp'][:10]}",
        f"**Status**: {report['status']}",
        "",
        "## Queue Health",
        "",
        f"| Metric | Count |",
        f"|---|---|",
        f"| Total Leads | {report['post_refresh_count']} |",
        f"| Main Queue (callable) | {report['queue_counts']['MAIN_QUEUE']} |",
        f"| Fresh Callable (CALL NOW + NEXT) | {report['queue_counts']['FRESH_CALL_NOW'] + report['queue_counts']['FRESH_NEXT']} |",
        f"| FRESH_CALL_NOW | {report['queue_counts']['FRESH_CALL_NOW']} |",
        f"| FRESH_NEXT | {report['queue_counts']['FRESH_NEXT']} |",
        f"| Already Contacted | {report['queue_counts']['ALREADY_CONTACTED']} |",
        f"| Verification Required | {report['queue_counts']['VERIFICATION_REQUIRED']} |",
        f"| Suppressed | {report['queue_counts']['SUPPRESSED']} |",
        f"| Quarantined | {report['queue_counts']['QUARANTINED']} |",
        "",
        "## Cleanup Summary",
        "",
        f"- New leads: **{m['new_leads']}**",
        f"- Fresh callable leads: **{m['fresh_callable_leads']}**",
        f"- Leads archived (stale 30d): **{m['leads_archived']}**",
        f"- Duplicates removed: **{m['duplicates_removed']}**",
        f"- Bad numbers detected: **{m['bad_numbers_detected']}**",
        f"- Bad numbers suppressed: **{m['bad_numbers_suppressed']}**",
        f"- DNC records suppressed: **{m['dnc_suppressed']}**",
        f"- Replacement phones found: **{m['replacement_phones_found']}**",
        f"- Founder comments processed: **{m['founder_comments_processed']}**",
        f"- Callbacks scheduled: **{m['callbacks_scheduled']}**",
        "",
        "## Top 10 Leads",
        "",
        f"| Rank | ID | Contact | Phone | Vertical | Priority | Freshness |",
        f"|---|---|---|---|---|---|---|",
    ]
    for t in top10:
        lines.append(
            f"| {t['rank']} | {t['id']} | {t['contact']} | {t['phone']} | "
            f"{t['vertical']} | {t['priority_score']} | {t['freshness_label']} |"
        )

    lines.extend([
        "",
        "## Top 25 Gate",
        "",
        f"**Pass**: {'YES' if report['top25_gate_pass'] else 'NO'}",
        "",
        "---",
        "",
        "## TODAY'S JOB",
        "",
        "1. Start at Dialer Rank #1.",
        "2. Call the fresh Tier-1 leads first (FRESH_CALL_NOW).",
        "3. Follow the callback schedule.",
        "4. Record the outcome/comment after each meaningful call.",
        "5. Mark bad numbers immediately.",
        "6. Do not manually clean spreadsheets.",
        "",
        f"*Report generated at {report['timestamp']}*",
    ])

    REPORT_MD.write_text("\n".join(lines), encoding="utf-8")


def _print_todays_job(report: Dict[str, Any]) -> None:
    """Print the founder's daily task list."""
    m = report["metrics"]
    print("\n" + "=" * 75)
    print("  TODAY'S JOB")
    print("=" * 75)
    print(f"  1. Start at Dialer Rank #1.")
    print(f"  2. Call the {report['queue_counts']['FRESH_CALL_NOW']} FRESH_CALL_NOW leads first.")
    print(f"  3. Then work through {report['queue_counts']['FRESH_NEXT']} FRESH_NEXT leads.")
    print(f"  4. Follow {m['callbacks_scheduled']} callback(s) scheduled today.")
    print(f"  5. Record the outcome/comment after each meaningful call.")
    print(f"  6. Mark bad numbers immediately — they are permanently suppressed.")
    print(f"  7. Do not manually clean spreadsheets.")
    print(f"")
    print(f"  HEALTH: {report['queue_counts']['MAIN_QUEUE']} callable leads in queue.")
    print(f"  BAD NUMBERS CLEANED: {m['bad_numbers_suppressed']} permanently suppressed this run.")
    print(f"  TOP 25 GATE: {'PASS' if report['top25_gate_pass'] else 'FAIL'}")
    print("=" * 75)


# ── Audit ──────────────────────────────────────────────────────────────────

def audit() -> None:
    """Audit the current dialer DB without making changes."""
    leads = _load_leads()
    print_audit(leads, "DIALER DATABASE (current)")

    # Check for bad numbers in the active queue
    suppressed = load_suppression_index()
    bad_in_queue = []
    for lead in leads:
        state = get_callable_state(lead)
        if state["main_queue"]:
            phone = _norm_phone(lead.get("phone") or "")
            if phone in suppressed:
                bad_in_queue.append(lead)

    if bad_in_queue:
        print(f"\n  WARNING: {len(bad_in_queue)} suppressed phones found in active queue!")
        for lead in bad_in_queue:
            print(f"    - {lead.get('phone')} ({lead.get('contact')}) [{lead.get('id')}]")
    else:
        print("\n  OK: No suppressed phones in active queue.")

    # Check founder comments
    comments = _load_founder_comments()
    bad_comments = [c for c in comments if classify_comment(
        f"{c.get('status', '')} {c.get('note', '')}"
    )["classification"] in ("BAD_NUMBER", "DNC", "WRONG_PERSON")]
    if bad_comments:
        print(f"\n  {len(bad_comments)} founder comments with suppression signals (processed by daily refresh).")


# ── CLI ────────────────────────────────────────────────────────────────────

def main() -> int:
    ap = argparse.ArgumentParser(description="MBM Dialer Daily Refresh + Bad-Number Cleanup")
    ap.add_argument("--dry-run", action="store_true", help="report only, no write")
    ap.add_argument("--audit", action="store_true", help="audit current DB")
    args = ap.parse_args()

    if args.audit:
        audit()
        return 0

    result = run_daily_refresh(dry_run=args.dry_run)
    if result.get("top25_gate_pass"):
        print("\nTOP25_GATE=PASS")
    else:
        print("\nTOP25_GATE=FAIL")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
