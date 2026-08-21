"""
GTM SELLER STATE INTERPRETER & NEXT-BEST-ACTION ENGINE
=============================================================================
Consumes REAL seller events recorded in the GtmSalesLedger (by Terminal 1's
batch runner / follow-up cascade) and derives, per seller:

  interpreted lifecycle state -> priority tier -> exactly ONE next action.

ZERO-FABRICATION RULES:
  - Only prospects that actually appear in the ledger are returned.
  - States are derived exclusively from recorded ledger events.
  - A property record alone never implies motivation or qualification.
  - Terminal states (DNC / INVALID) are excluded from active ranking.

PRIORITY ORDER (highest commercial priority first):
  1. active conversation   (CONTACTED / ENGAGED)
  2. callback due          (CALLBACK_REQUESTED)
  3. interested            (INTERESTED)
  4. qualified             (QUALIFIED / AUDIT_OFFERED)
  5. appointment due       (APPOINTMENT_* / MEETING_*)
  6. offer follow-up       (OFFER_* / CHECKOUT_SENT / PROPOSAL / NEGOTIATION)
  7. new verified seller   (initial outreach sent / queued / no-answer)
  8. nurture               (NOT_INTERESTED, post-WON)

Within a tier the OLDEST pending event is surfaced first (most overdue).
=============================================================================
"""

from typing import Any, Dict, List, Optional
import re

# The exact ONE next action per interpreted state.
ACTION_CALLBACK = "CALLBACK"
ACTION_FOLLOW_UP = "FOLLOW_UP"
ACTION_QUALIFY = "QUALIFY"
ACTION_BOOK_APPOINTMENT = "BOOK_APPOINTMENT"
ACTION_PREPARE_OFFER = "PREPARE_OFFER"
ACTION_NURTURE = "NURTURE"
ACTION_DNC = "DNC"
ACTION_WAIT = "WAIT"

# tier rank -> (tier name, next action)
_TIER_ACTIVE_CONVERSATION = (1, "ACTIVE_CONVERSATION", ACTION_QUALIFY)
_TIER_CALLBACK_DUE = (2, "CALLBACK_DUE", ACTION_CALLBACK)
_TIER_INTERESTED = (3, "INTERESTED", ACTION_BOOK_APPOINTMENT)
_TIER_QUALIFIED = (4, "QUALIFIED", ACTION_BOOK_APPOINTMENT)
_TIER_APPOINTMENT_DUE = (5, "APPOINTMENT_DUE", ACTION_PREPARE_OFFER)
_TIER_OFFER_FOLLOWUP = (6, "OFFER_FOLLOWUP", ACTION_FOLLOW_UP)
_TIER_NEW_VERIFIED = (7, "NEW_VERIFIED_SELLER", ACTION_WAIT)
_TIER_NEEDS_RETRY = (7, "NEW_VERIFIED_SELLER", ACTION_FOLLOW_UP)
_TIER_NURTURE = (8, "NURTURE", ACTION_NURTURE)

# Recorded ledger new_state -> (tier_rank, tier_name, next_action, terminal)
_STATE_MAP: Dict[str, tuple] = {
    # Active conversation
    "CONTACTED": _TIER_ACTIVE_CONVERSATION,
    "ENGAGED": _TIER_ACTIVE_CONVERSATION,
    "CONVERSATION": _TIER_ACTIVE_CONVERSATION,
    # Callback
    "CALLBACK_REQUESTED": _TIER_CALLBACK_DUE,
    "CALLBACK": _TIER_CALLBACK_DUE,
    # Interested
    "INTERESTED": _TIER_INTERESTED,
    # Qualified
    "QUALIFIED": _TIER_QUALIFIED,
    "AUDIT_OFFERED": _TIER_QUALIFIED,
    # Appointment
    "APPOINTMENT": _TIER_APPOINTMENT_DUE,
    "APPOINTMENT_BOOKED": _TIER_APPOINTMENT_DUE,
    "APPOINTMENT_SCHEDULED": _TIER_APPOINTMENT_DUE,
    "MEETING_BOOKED": _TIER_APPOINTMENT_DUE,
    "MEETING_COMPLETED": _TIER_APPOINTMENT_DUE,
    # Offer stage
    "OFFER_MADE": _TIER_OFFER_FOLLOWUP,
    "OFFER_SENT": _TIER_OFFER_FOLLOWUP,
    "CHECKOUT_SENT": _TIER_OFFER_FOLLOWUP,
    "PROPOSAL": _TIER_OFFER_FOLLOWUP,
    "NEGOTIATION": _TIER_OFFER_FOLLOWUP,
    # Early funnel — outreach dispatched, awaiting response
    "WHATSAPP_SENT": _TIER_NEW_VERIFIED,
    "EMAIL_SENT": _TIER_NEW_VERIFIED,
    "SMS_SENT": _TIER_NEW_VERIFIED,
    # Link generated but NOT confirmed sent: nothing to do until operator sends.
    "WHATSAPP_LINK_READY": _TIER_NEW_VERIFIED,
    "CASCADE_QUEUED": _TIER_NEW_VERIFIED,
    # Failed contact attempts — cascade owns retry timing
    "NO_ANSWER": _TIER_NEEDS_RETRY,
    "VOICEMAIL": _TIER_NEEDS_RETRY,
    # Nurture / terminal
    "NOT_INTERESTED": _TIER_NURTURE,
    "WON": _TIER_NURTURE,
    "PURCHASED": _TIER_NURTURE,
    "DEAL_WON": _TIER_NURTURE,
    "REVENUE_RECEIVED": _TIER_NURTURE,
}

_TERMINAL_STATES = {"DNC", "INVALID", "WRONG_PERSON", "SUPPRESSED", "DO_NOT_CALL"}

# PRODUCTION VS FIXTURE RULE: test/fixture/synthetic ledger entries never count
# toward real seller production metrics or next-best-actions.
# Matching is SEGMENT-based ("LEAD_IDEMPOTENT_01" -> {LEAD, IDEMPOTENT, 01}) so
# ordinary IDs like "M-LATEST" (which merely contains the letters t-e-s-t) are
# never misclassified.
_FIXTURE_SEGMENTS = {"TEST", "E2E", "SIM", "MOCK", "FIXTURE", "DEMO", "SAMPLE", "IDEMPOTENT"}


def is_fixture_event(event: Dict[str, Any]) -> bool:
    """True when a ledger event is a test/fixture entry, not production evidence."""
    pid = str(event.get("prospect_id") or "").upper()
    segments = set(re.split(r"[^A-Z0-9]+", pid))
    return bool(segments & _FIXTURE_SEGMENTS)


def production_events(events: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    """Filter a ledger down to persisted PRODUCTION events only."""
    return [e for e in (events or []) if not is_fixture_event(e)]


def interpret_seller_events(events: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Interpret real ledger events into per-seller state.

    Returns {prospect_id: interpretation}. Only ledgered prospects appear;
    an empty ledger yields an empty dict (nothing is invented).
    """
    interpreted: Dict[str, Dict[str, Any]] = {}
    for e in production_events(events):
        pid = str(e.get("prospect_id") or "").strip()
        if not pid:
            continue
        state = str(e.get("new_state") or "").upper()
        ts = str(e.get("timestamp") or "")
        prev = interpreted.get(pid)
        # Ledger is append-only; the LAST event wins as current state.
        if prev and str(prev.get("last_timestamp") or "") >= ts:
            continue

        if state in _TERMINAL_STATES:
            interp = {
                "prospect_id": pid,
                "state": state,
                "tier_rank": 99,
                "tier": "TERMINAL",
                "next_action": ACTION_DNC,
                "terminal": True,
                "last_timestamp": ts,
                "last_action": e.get("action"),
                "channel": e.get("channel"),
                "evidence": e.get("evidence") or {},
            }
        else:
            tier_rank, tier_name, action = _STATE_MAP.get(state, (7, "NEW_VERIFIED_SELLER", ACTION_WAIT))
            interp = {
                "prospect_id": pid,
                "state": state,
                "tier_rank": tier_rank,
                "tier": tier_name,
                "next_action": action,
                "terminal": False,
                "last_timestamp": ts,
                "last_action": e.get("action"),
                "channel": e.get("channel"),
                "evidence": e.get("evidence") or {},
            }
        interpreted[pid] = interp
    return interpreted


def rank_active_sellers(
    interpreted: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Order active (non-terminal) sellers by commercial priority.

    Priority: tier rank asc, then OLDEST pending event first (most overdue).
    Exactly one next action per seller is included in each entry.
    """
    active = [s for s in interpreted.values() if not s.get("terminal")]
    active.sort(key=lambda s: (s["tier_rank"], str(s.get("last_timestamp") or "")))
    return active


def seller_pipeline_summary(interpreted: Dict[str, Dict[str, Any]]) -> Dict[str, int]:
    """Count sellers per priority tier (recorded prospects only)."""
    summary: Dict[str, int] = {}
    for s in interpreted.values():
        summary[s["tier"]] = summary.get(s["tier"], 0) + 1
    return summary
