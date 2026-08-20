#!/usr/bin/env python3
"""
MBM Dialer Canonical Queue Engine
=================================
SINGLE SOURCE OF TRUTH for lead callability, queue eligibility, and ordering.

Everything that renders a dialer queue — the React UI, the reconcile/push
scripts, the digital-services importer, the verification gate, the audit —
MUST derive state through `get_callable_state(lead)` and order through
`rank_main_queue(leads)`. No component may re-sort independently.

States (evaluated in this exact order):

  HARD SUPPRESSION       DNC / DO_NOT_CALL / BAD_NUMBER / WRONG_NUMBER /
                         WRONG_PERSON / TENANT / RELATIVE_OR_ASSOCIATE /
                         NON_OWNER / QUARANTINED / SUPPRESSED
                         -> callable=False, main_queue=False
  BLOCKED VERIFICATION   missing/invalid/unverified phone, placeholder
                         identity, failed verification gate
                         -> callable=False, main_queue=False
  ALREADY CONTACTED      attempts > 0 OR disposition exists OR last_touch
                         -> preserved in history, OUT of NEW/CALL-NOW queue
  UNTOUCHED              attempts==0, no disposition, verified phone + id,
                         not suppressed
                         -> UNCALLED_VERIFIED, main_queue=True

The main dialer queue contains ONLY: UNCALLED + VERIFIED + CALLABLE, ordered:

  1. NEWLY_IMPORTED   (imported_at/created_at/first_seen_at recent)
  2. NEWLY_VERIFIED   (verified_at recent)
  3. NEWLY_ENRICHED   (enriched/updated recent)
  4. highest intent
  5. highest callability
  6. highest motivation/deal score
  7. freshest discovered_at / imported_at

Legacy records with no timestamps are treated as OLD — never as NEW.

Queues (canonical buckets):
  FRESH_CALL_NOW | FRESH_NEXT | UNCALLED_VERIFIED | ALREADY_CONTACTED |
  VERIFICATION_REQUIRED | SUPPRESSED | QUARANTINED
"""

from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from MBM.LeadEngine.dialer_verification_gate import (
    check_lead,
    is_valid_phone,
    is_placeholder_identity,
)

SUPPRESSION_FILE = ROOT_DIR / "MBM" / "Artifacts" / "suppressed_bad_phones.json"

# ── Canonical constants ────────────────────────────────────────────────────

# Dispositions/states that PERMANENTLY remove a lead from the callable queue.
HARD_SUPPRESSION_DISPOSITIONS = {
    "DNC",
    "DO_NOT_CALL",
    "BAD_NUMBER",
    "WRONG_NUMBER",
    "WRONG_PERSON",
    "TENANT",
    "RELATIVE_OR_ASSOCIATE",
    "NON_OWNER",
    "QUARANTINED",
    "SUPPRESSED",
}

# Buckets that never enter the main queue.
NON_MAIN_BUCKETS = {
    "ALREADY_CONTACTED",
    "VERIFICATION_REQUIRED",
    "SUPPRESSED",
    "QUARANTINED",
}

MAIN_BUCKETS = ("FRESH_CALL_NOW", "FRESH_NEXT", "UNCALLED_VERIFIED")

QUEUE_ORDER = (
    "FRESH_CALL_NOW",
    "FRESH_NEXT",
    "UNCALLED_VERIFIED",
    "ALREADY_CONTACTED",
    "VERIFICATION_REQUIRED",
    "SUPPRESSED",
    "QUARANTINED",
)

FRESHNESS_STAGE_RANK = {
    "NEWLY_IMPORTED": 0,
    "NEWLY_VERIFIED": 1,
    "NEWLY_ENRICHED": 2,
    "OLD": 3,
}

# State fields that can carry a REAL call/disposition/suppression signal.
# Neutral quality/status labels (status, stage, callability_status,
# identity_state) are NOT contact signals and are excluded so a lead is never
# misclassified as contacted (or contacted twice) by its own derived labels.
_DISPOSITION_FIELDS = (
    "disposition",
    "outcome",
    "suppression_state",
    "suppression_reason",
)

_TIMESTAMP_FIELDS = (
    "imported_at",
    "created_at",
    "first_seen_at",
    "source_timestamp",
    "discovered_at",
    "verified_at",
    "retrieved_at",
    "source_date",
    "observed_at",
    "last_enriched_at",
    "enriched_at",
    "updated_at",
    "skip_trace_verified_at",
)

# Positive/soft dispositions that still mean the lead was contacted.
ALREADY_CONTACTED_TOKENS = (
    "ANSWERED",
    "PITCHED",
    "VOICEMAIL",
    "NO-ANSWER",
    "NO_ANSWER",
    "BUSY",
    "CALL_BACK",
    "CALLBACK",
    "FOLLOW",
    "NURTURE",
    "MEETING",
    "QUALIFIED",
    "WARMED",
    "CONTACTED",
    "NOT_INTERESTED",
    "PROPOSAL",
    "DEAL",
    "WON",
    "BOOKED",
    "CONNECTED",
)


def _norm_phone(p: Any) -> str:
    digits = "".join(ch for ch in str(p or "") if ch.isdigit())
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def load_suppression_index() -> set:
    """Return the set of permanently suppressed (bad/opt-out) normalized phones."""
    suppressed: set = set()
    if SUPPRESSION_FILE.exists():
        try:
            data = json.loads(SUPPRESSION_FILE.read_text(encoding="utf-8"))
            for p in data.get("suppressed_phones", []):
                suppressed.add(_norm_phone(p))
        except Exception:
            pass
    return suppressed


_SUPPRESSION_INDEX = None


def get_suppression_index() -> set:
    global _SUPPRESSION_INDEX
    if _SUPPRESSION_INDEX is None:
        _SUPPRESSION_INDEX = load_suppression_index()
    return _SUPPRESSION_INDEX


def _to_upper(value: Any) -> str:
    return str(value or "").upper()


def _has_suppression_token(value: Any) -> bool:
    upper = _to_upper(value)
    if not upper:
        return False
    for token in HARD_SUPPRESSION_DISPOSITIONS:
        if token in upper:
            return True
    return False


def _is_flag(lead: Dict[str, Any], keys: Tuple[str, ...]) -> bool:
    for key in keys:
        v = lead.get(key)
        if v is True or _to_upper(v) in ("TRUE", "1", "YES"):
            return True
    return False


def _is_suppressed_flag(lead: Dict[str, Any]) -> bool:
    for key in ("suppressed", "is_suppressed", "bad_number", "is_bad_number"):
        v = lead.get(key)
        if v is True or _to_upper(v) in ("TRUE", "1", "YES"):
            return True
    if _to_upper(lead.get("sms_opted_out")) in ("TRUE", "1", "YES"):
        return True
    return False


def _disposition_of(lead: Dict[str, Any]) -> str:
    for field in _DISPOSITION_FIELDS:
        value = lead.get(field) or (lead.get("details") or {}).get(field) or ""
        value = _to_upper(value)
        if value and value not in ("", "NONE", "NULL", "NA", "UNKNOWN"):
            return value
    return ""


def _attempts_of(lead: Dict[str, Any]) -> int:
    try:
        return int(lead.get("attempts") or lead.get("call_attempts") or 0)
    except (TypeError, ValueError):
        return 0


def _last_touch_of(lead: Dict[str, Any]) -> Optional[str]:
    for key in ("last_touch", "last_attempt_at", "called_at", "last_contacted_at", "last_disposition"):
        v = lead.get(key) or (lead.get("details") or {}).get(key)
        if v:
            return str(v)
    return None


def _parse_ts(value: Any) -> Optional[float]:
    """Parse an ISO timestamp string into epoch seconds; None if unparseable."""
    if not value:
        return None
    s = str(value).strip()
    if not s or s.lower() in ("none", "null", "n/a", "unknown", "legacy"):
        return None
    for fmt in (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            dt = datetime.strptime(s, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except ValueError:
            continue
    return None


def _newest_timestamp(lead: Dict[str, Any]) -> Optional[float]:
    best = None
    for field in _TIMESTAMP_FIELDS:
        value = lead.get(field) or (lead.get("details") or {}).get(field)
        ts = _parse_ts(value)
        if ts is not None:
            best = max(best, ts) if best is not None else ts
    return best


def freshness_stage_of(lead: Dict[str, Any]) -> Tuple[str, int, int]:
    """Return (stage, freshness_score, newest_epoch).

    NEWLY_IMPORTED -> first imported/seen/created within 3 days
    NEWLY_VERIFIED -> verified_at within 4 days
    NEWLY_ENRICHED -> enriched/updated within 5 days
    OLD            -> everything else (legacy timestamps are never NEW)
    """
    now = datetime.now(timezone.utc)
    newest = _newest_timestamp(lead)

    def within(days: int, value: Any) -> bool:
        ts = _parse_ts(value)
        if ts is None:
            return False
        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
        return (now - dt) <= timedelta(days=days)

    is_new_today = lead.get("new_today") is True or _to_upper(lead.get("new_today")) == "TRUE"

    imported_signal = (
        lead.get("imported_at")
        or lead.get("first_seen_at")
        or (lead.get("details") or {}).get("first_seen_at")
        or lead.get("source_timestamp")
        or lead.get("created_at")
        or lead.get("discovered_at")
        or lead.get("retrieved_at")
    )
    if is_new_today and (within(3, lead.get("imported_at")) or within(3, lead.get("first_seen_at")) or within(3, lead.get("source_timestamp")) or within(3, lead.get("retrieved_at")) or within(3, lead.get("discovered_at"))):
        return "NEWLY_IMPORTED", 95, newest or 0.0
    if imported_signal and within(3, imported_signal):
        return "NEWLY_IMPORTED", 95, newest or 0.0

    verified_signal = lead.get("verified_at") or (lead.get("details") or {}).get("verified_at")
    if verified_signal and within(4, verified_signal):
        return "NEWLY_VERIFIED", 85, newest or 0.0

    enriched_signal = (
        lead.get("last_enriched_at")
        or lead.get("enriched_at")
        or lead.get("updated_at")
        or lead.get("skip_trace_verified_at")
    )
    if enriched_signal and within(5, enriched_signal):
        return "NEWLY_ENRICHED", 70, newest or 0.0

    return "OLD", 25, newest or 0.0


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def priority_score_of(lead: Dict[str, Any]) -> int:
    """Composite priority 0-100: intent * 0.35 + callability * 0.25 + deal/motivation * 0.20 + freshness * 0.20."""
    intent = _as_int(lead.get("intent_score"))
    if not intent:
        motivation = _as_int(lead.get("motivation_score"))
        deal = _as_int(lead.get("deal_score"))
        intent = max(motivation, deal)
    callability = _as_int(lead.get("callability_score"), 90)
    if not callability:
        callability = 90
    deal = _as_int(lead.get("deal_score"))
    motivation = _as_int(lead.get("motivation_score"))
    strength = max(deal, motivation)
    freshness = _as_int(lead.get("freshness_score"), 25)
    return min(100, round(0.35 * intent + 0.25 * callability + 0.20 * strength + 0.20 * freshness))


def _main_queue_sort_key(lead: Dict[str, Any]) -> Tuple[int, int, int, int, int, float, str]:
    state = lead.get("_callable_state") or get_callable_state(lead)
    stage_rank = FRESHNESS_STAGE_RANK.get(state["freshness_stage"], 3)

    intent = _as_int(lead.get("intent_score"))
    if not intent:
        intent = max(_as_int(lead.get("motivation_score")), _as_int(lead.get("deal_score")))
    callability = _as_int(lead.get("callability_score"), 90)
    if not callability:
        callability = 90
    strength = max(_as_int(lead.get("motivation_score")), _as_int(lead.get("deal_score")))
    newest = state["newest_timestamp_epoch"] or 0.0
    prio = state.get("priority_score") or priority_score_of(lead)

    # 1. Freshness Stage (NEWLY_IMPORTED=0, NEWLY_VERIFIED=1, NEWLY_ENRICHED=2, OLD=3)
    # 2. -Priority Score
    # 3. -Intent
    # 4. -Callability
    # 5. -Strength (Motivation/Deal)
    # 6. -Newest Timestamp Epoch
    # 7. Stable ID
    return (stage_rank, -prio, -intent, -callability, -strength, -newest, str(lead.get("id") or ""))


def get_callable_state(lead: Dict[str, Any]) -> Dict[str, Any]:
    """THE canonical callability/eligibility function (see module docstring).

    Returns a dict every consumer must read; never re-derive eligibility.
    """
    disposition = _disposition_of(lead)
    attempts = _attempts_of(lead)
    last_touch = _last_touch_of(lead)
    phone = _norm_phone(lead.get("phone") or (lead.get("details") or {}).get("Owner_Phone") or "")

    suppression_reason: Optional[str] = None
    blocked_reason: Optional[str] = None
    already_contacted = False
    uncalled_verified = False

    # ── 1. HARD SUPPRESSION ──────────────────────────────────────────────
    if _is_flag(lead, ("quarantined", "is_quarantined")):
        suppression_reason = "QUARANTINED"
    elif _is_suppressed_flag(lead):
        suppression_reason = "SUPPRESSED_FLAG"
    elif _has_suppression_token(disposition):
        suppression_reason = disposition
    elif _has_suppression_token(lead.get("identity_state") or (lead.get("details") or {}).get("identity_state")):
        suppression_reason = _to_upper(lead.get("identity_state") or (lead.get("details") or {}).get("identity_state"))
    elif phone and phone in get_suppression_index():
        suppression_reason = "SUPPRESSED_PHONE_INDEX"

    if suppression_reason:
        quarantined = "QUARANTINED" in suppression_reason or "QUARANTINE" in suppression_reason
        return {
            "callable": False,
            "main_queue": False,
            "already_contacted": False,
            "uncalled_verified": False,
            "queue_bucket": "QUARANTINED" if quarantined else "SUPPRESSED",
            "suppression_reason": suppression_reason,
            "blocked_reason": None,
            "verification_status": str(lead.get("verification_status") or "SUPPRESSED"),
            "callability_status": "SUPPRESSED",
            "freshness_stage": "OLD",
            "freshness_score": 0,
            "priority_score": 0,
            "newest_timestamp_epoch": 0.0,
            "attempts": attempts,
            "disposition": disposition,
            "last_touch": last_touch,
        }

    # ── 2. BLOCKED VERIFICATION ──────────────────────────────────────────
    gate = check_lead(lead)
    gate_passed = gate["passed"]
    placeholder = is_placeholder_identity(lead)
    if not gate_passed or placeholder:
        if placeholder:
            blocked_reason = "PLACEHOLDER_IDENTITY"
        elif not gate["phone_ok"]:
            blocked_reason = f"INVALID_PHONE:{gate['phone_reason']}"
        elif not gate["verified_ok"]:
            blocked_reason = f"UNVERIFIED:{gate['verified_source']}"
        elif not gate["name_ok"]:
            blocked_reason = f"INVALID_NAME:{gate['name_reason']}"
        return {
            "callable": False,
            "main_queue": False,
            "already_contacted": False,
            "uncalled_verified": False,
            "queue_bucket": "VERIFICATION_REQUIRED",
            "suppression_reason": None,
            "blocked_reason": blocked_reason,
            "verification_status": str(lead.get("verification_status") or "VERIFICATION_REQUIRED"),
            "callability_status": "VERIFICATION_REQUIRED",
            "freshness_stage": "OLD",
            "freshness_score": 0,
            "priority_score": 0,
            "newest_timestamp_epoch": 0.0,
            "attempts": attempts,
            "disposition": disposition,
            "last_touch": last_touch,
        }

    # ── 3. ALREADY CALLED ────────────────────────────────────────────────
    if attempts > 0 or disposition or last_touch:
        already_contacted = True
        return {
            "callable": False,
            "main_queue": False,
            "already_contacted": True,
            "uncalled_verified": False,
            "queue_bucket": "ALREADY_CONTACTED",
            "suppression_reason": None,
            "blocked_reason": None,
            "verification_status": str(lead.get("verification_status") or "VERIFIED"),
            "callability_status": "ALREADY_CONTACTED",
            "freshness_stage": "OLD",
            "freshness_score": 0,
            "priority_score": priority_score_of(lead),
            "newest_timestamp_epoch": _newest_timestamp(lead) or 0.0,
            "attempts": attempts,
            "disposition": disposition,
            "last_touch": last_touch,
        }

    # ── 4. UNTOUCHED / UNCALLED + VERIFIED + CALLABLE ────────────────────
    stage, fresh_score, newest = freshness_stage_of(lead)
    uncalled_verified = True
    temp_lead = dict(lead)
    temp_lead["freshness_score"] = fresh_score
    prio_score = priority_score_of(temp_lead)
    return {
        "callable": True,
        "main_queue": True,
        "already_contacted": False,
        "uncalled_verified": True,
        "queue_bucket": "UNCALLED_VERIFIED",  # reassigned later to CALL_NOW/NEXT by rank
        "suppression_reason": None,
        "blocked_reason": None,
        "verification_status": str(lead.get("verification_status") or "VERIFIED"),
        "callability_status": "VERIFIED",
        "freshness_stage": stage,
        "freshness_score": fresh_score,
        "priority_score": prio_score,
        "newest_timestamp_epoch": newest,
        "attempts": attempts,
        "disposition": disposition,
        "last_touch": last_touch,
    }


def rank_main_queue(leads: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """THE canonical global ordering. Returns only UNCALLED+VERIFIED+CALLABLE,
    sorted by the single cross-niche priority rule. Every niche (Real Estate
    Sellers, Cash Buyers, Digital Services, Clinics, Dental, Chiropractic,
    ConTech, B2B, ...) competes with the same rules."""
    eligible = []
    for lead in leads:
        state = get_callable_state(lead)
        lead["_callable_state"] = state
        if state["main_queue"]:
            eligible.append(lead)
    eligible.sort(key=_main_queue_sort_key)
    return eligible


def assign_lead_metadata(lead: Dict[str, Any], state: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Normalize the required per-lead fields. Preserves all history, stamps explicit freshness and ranking fields."""
    state = state or get_callable_state(lead)
    now = datetime.now(timezone.utc).isoformat()

    # Discover dates
    if not lead.get("discovered_at"):
        for key in ("first_seen_at", "source_timestamp", "retrieved_at", "source_date", "observed_at", "created_at"):
            if lead.get(key):
                lead["discovered_at"] = str(lead[key])
                break
        if not lead.get("discovered_at") and state.get("newest_timestamp_epoch"):
            lead["discovered_at"] = datetime.fromtimestamp(state["newest_timestamp_epoch"], tz=timezone.utc).isoformat()

    if not lead.get("imported_at"):
        lead["imported_at"] = lead.get("discovered_at") or now

    if not lead.get("verified_at"):
        if lead.get("skip_trace_status") == "VERIFIED" or lead.get("owner_status") == "VERIFIED_OWNER" or state.get("verification_status", "").startswith("VERIFIED"):
            lead["verified_at"] = lead.get("discovered_at") or lead.get("imported_at") or now

    lead.setdefault("attempts", 0)
    if not lead.get("attempts"):
        lead["attempts"] = 0

    if not lead.get("category"):
        lead["category"] = lead.get("vertical") or "UNCATEGORIZED"
    if not lead.get("source"):
        lead["source"] = (lead.get("details") or {}).get("source") or lead.get("source_reference") or "UNKNOWN"

    fresh_stage = state["freshness_stage"]
    fresh_score = state["freshness_score"]
    lead["callability_status"] = state["callability_status"]
    lead["verification_status"] = state["verification_status"]
    lead["freshness_score"] = fresh_score
    lead["priority_score"] = state["priority_score"]
    lead["freshness_stage"] = fresh_stage
    lead["callable"] = state["callable"]
    lead["main_queue"] = state["main_queue"]
    lead["already_contacted"] = state["already_contacted"]
    lead["uncalled_verified"] = state["uncalled_verified"]
    lead["queue_bucket"] = state["queue_bucket"]
    lead["suppression_reason"] = state["suppression_reason"]
    lead["blocked_reason"] = state["blocked_reason"]
    lead["queue_evaluated_at"] = now

    # Explicit badges
    lead["new_today"] = (fresh_stage in ("NEWLY_IMPORTED", "NEWLY_VERIFIED") or fresh_score >= 80 or lead.get("new_today") is True)
    if fresh_stage == "NEWLY_IMPORTED":
        lead["freshness_label"] = "JUST FOUND"
    elif fresh_stage == "NEWLY_VERIFIED":
        lead["freshness_label"] = "RECENTLY VERIFIED"
    elif fresh_stage == "NEWLY_ENRICHED":
        lead["freshness_label"] = "RECENTLY ENRICHED"
    elif fresh_score >= 80:
        lead["freshness_label"] = "FRESH"
    else:
        lead["freshness_label"] = "EXISTING"

    return lead


def build_global_queue(leads: List[Dict[str, Any]], call_now_size: int = 25, next_size: int = 75) -> Dict[str, List[Dict[str, Any]]]:
    """Partition ALL leads into the canonical queue sections, ordered.

    FRESH_CALL_NOW = top `call_now_size` of the ranked main queue
    FRESH_NEXT     = next `next_size`
    UNCALLED_VERIFIED = remaining main queue
    then ALREADY_CONTACTED, VERIFICATION_REQUIRED, SUPPRESSED, QUARANTINED.
    """
    buckets: Dict[str, List[Dict[str, Any]]] = {b: [] for b in QUEUE_ORDER}

    ranked = rank_main_queue(leads)
    main_ids = {str(l.get("id")) for l in ranked}

    # Track category ranks
    category_counters: Dict[str, int] = {}

    for idx, lead in enumerate(ranked):
        assign_lead_metadata(lead)
        lead["priority_rank"] = idx + 1
        cat = lead.get("vertical") or lead.get("category") or "UNKNOWN"
        category_counters[cat] = category_counters.get(cat, 0) + 1
        lead["category_rank"] = category_counters[cat]

        if idx < call_now_size:
            lead["queue_bucket"] = "FRESH_CALL_NOW"
            lead["partition"] = "CALL_NOW"
        elif idx < call_now_size + next_size:
            lead["queue_bucket"] = "FRESH_NEXT"
            lead["partition"] = "NEXT"
        else:
            lead["queue_bucket"] = "UNCALLED_VERIFIED"
            lead["partition"] = "VERIFIED_ACTIVE"

    buckets["FRESH_CALL_NOW"] = ranked[:call_now_size]
    buckets["FRESH_NEXT"] = ranked[call_now_size:call_now_size + next_size]
    buckets["UNCALLED_VERIFIED"] = ranked[call_now_size + next_size:]

    for lead in leads:
        if str(lead.get("id")) in main_ids:
            continue  # already placed in a main bucket
        state = lead.get("_callable_state") or get_callable_state(lead)
        assign_lead_metadata(lead, state)
        bucket = state["queue_bucket"]
        if bucket not in buckets:
            bucket = "VERIFICATION_REQUIRED"
        lead["queue_bucket"] = bucket
        lead["partition"] = bucket
        buckets[bucket].append(lead)

    # Deterministic secondary order inside non-main buckets.
    for bucket in ("ALREADY_CONTACTED", "VERIFICATION_REQUIRED", "SUPPRESSED", "QUARANTINED"):
        buckets[bucket].sort(
            key=lambda l: (
                -(l.get("_callable_state") or get_callable_state(l)).get("priority_score", 0),
                str(l.get("id") or ""),
            )
        )

    return buckets


def ordered_db_records(buckets: Dict[str, List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Flatten buckets into the canonical DB order (main queue first)."""
    records: List[Dict[str, Any]] = []
    for bucket in QUEUE_ORDER:
        for lead in buckets.get(bucket, []):
            if "_callable_state" in lead:
                del lead["_callable_state"]
            records.append(lead)
    return records


# ── Audit ──────────────────────────────────────────────────────────────────

def audit_counts(leads: List[Dict[str, Any]]) -> Dict[str, int]:
    counts: Dict[str, int] = {
        "TOTAL": len(leads),
        "MAIN_QUEUE": 0,
        "FRESH_CALL_NOW": 0,
        "FRESH_NEXT": 0,
        "UNCALLED_VERIFIED": 0,
        "NEW_VERIFIED": 0,
        "ALREADY_CONTACTED": 0,
        "BAD_NUMBER": 0,
        "DO_NOT_CALL": 0,
        "WRONG_NUMBER": 0,
        "WRONG_PERSON": 0,
        "VERIFICATION_REQUIRED": 0,
        "QUARANTINED": 0,
        "SUPPRESSED": 0,
    }
    for lead in leads:
        state = get_callable_state(lead)
        bucket = lead.get("queue_bucket") or state["queue_bucket"]
        if bucket in counts:
            counts[bucket] += 1
        else:
            counts[bucket] = 1
        if state["main_queue"]:
            counts["MAIN_QUEUE"] += 1
            if state["freshness_stage"] in ("NEWLY_IMPORTED", "NEWLY_VERIFIED"):
                counts["NEW_VERIFIED"] += 1
        disp = _disposition_of(lead)
        if "BAD_NUMBER" in disp:
            counts["BAD_NUMBER"] += 1
        if "DO_NOT_CALL" in disp or "DNC" in disp:
            counts["DO_NOT_CALL"] += 1
        if "WRONG_NUMBER" in disp:
            counts["WRONG_NUMBER"] += 1
        if "WRONG_PERSON" in disp:
            counts["WRONG_PERSON"] += 1
    counts["SUPPRESSED"] = sum(1 for l in leads if get_callable_state(l)["queue_bucket"] == "SUPPRESSED")
    return counts


def top_25_audit(ranked_main: List[Dict[str, Any]], limit: int = 25) -> Dict[str, Any]:
    """Validate the top-N main queue: attempts==0, disposition empty,
    callable True, verification passed."""
    problems = []
    rows = []
    for idx, lead in enumerate(ranked_main[:limit], 1):
        state = get_callable_state(lead)
        gate = check_lead(lead)
        row = {
            "rank": idx,
            "new_or_existing": "NEWLY_IMPORTED" if state["freshness_stage"] == "NEWLY_IMPORTED" else ("EXISTING" if state["freshness_stage"] == "OLD" else state["freshness_stage"]),
            "category": lead.get("vertical") or lead.get("category") or "",
            "contact": lead.get("contact") or lead.get("company") or "",
            "phone": lead.get("phone") or "",
            "attempts": state["attempts"],
            "disposition": state["disposition"],
            "verification_status": state["verification_status"],
            "freshness_score": state["freshness_score"],
            "priority_score": state["priority_score"],
        }
        rows.append(row)
        if state["attempts"] != 0:
            problems.append({"rank": idx, "id": lead.get("id"), "issue": "attempts!=0"})
        if state["disposition"]:
            problems.append({"rank": idx, "id": lead.get("id"), "issue": f"disposition={state['disposition']}"})
        if state["callable"] is not True:
            problems.append({"rank": idx, "id": lead.get("id"), "issue": "callable!=True"})
        if not gate["passed"]:
            problems.append({"rank": idx, "id": lead.get("id"), "issue": f"verification={gate['rejection_reasons']}"})
    return {"rows": rows, "problems": problems, "pass": not problems}


def print_audit(leads: List[Dict[str, Any]], label: str = "DIALER DATABASE") -> None:
    counts = audit_counts(leads)
    print("=" * 70)
    print(f"  {label} — CANONICAL QUEUE AUDIT")
    print("=" * 70)
    for key in (
        "TOTAL",
        "MAIN_QUEUE",
        "UNCALLED_VERIFIED",
        "NEW_VERIFIED",
        "ALREADY_CONTACTED",
        "BAD_NUMBER",
        "DO_NOT_CALL",
        "WRONG_NUMBER",
        "WRONG_PERSON",
        "VERIFICATION_REQUIRED",
        "QUARANTINED",
        "SUPPRESSED",
    ):
        print(f"  {key}: {counts.get(key, 0)}")

    ranked = rank_main_queue(leads)
    audit = top_25_audit(ranked)
    print("\n  TOP 25 MAIN QUEUE")
    print(f"  {'rank':<5}{'new_or_existing':<16}{'category':<26}{'contact':<26}{'phone':<16}{'att':<4}{'disp':<14}{'ver':<24}{'fresh':<6}{'prio':<5}")
    for r in audit["rows"]:
        print(f"  {r['rank']:<5}{str(r['new_or_existing'])[:14]:<16}{str(r['category'])[:24]:<26}{str(r['contact'])[:24]:<26}{str(r['phone'])[:14]:<16}{r['attempts']:<4}{str(r['disposition'])[:12]:<14}{str(r['verification_status'])[:22]:<24}{r['freshness_score']:<6}{r['priority_score']:<5}")

    if audit["problems"]:
        print("\n  ❌ TOP-25 VIOLATIONS FOUND:")
        for p in audit["problems"]:
            print(f"    {p}")
    else:
        print("\n  ✅ TOP-25 GATE: attempts==0 | disposition empty | callable=True | verification=PASS")
    print("=" * 70)
    return {"counts": counts, "top25_pass": not audit["problems"]}