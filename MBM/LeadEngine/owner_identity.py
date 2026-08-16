#!/usr/bin/env python3
"""
Owner Identity Verification Layer
=================================
Separates what the DATABASE proves about a property owner from what the
LIVE CALLER actually confirms on the phone.

Database-level ownership evidence (DCAD parcel records, verified owner name,
source_class=COUNTY_RECORD) is real, but it does NOT prove who answers the
call. This layer adds a mandatory, lightweight call-level identity capture and
a transparent identity score built ONLY from available evidence.

Identity states:
    OWNER_CONFIRMED             — caller identity confirmed AND matches verified record
    OWNER_LIKELY                — evidence strongly suggests owner, not yet call-confirmed
    AUTHORIZED_DECISION_MAKER   — caller confirmed as authorized decision-maker
    IDENTITY_UNCONFIRMED        — no supporting identity evidence
    WRONG_PERSON                — answered but NOT the owner / not authorized
    WRONG_NUMBER                — number does not reach the intended contact
    TENANT                      — caller is a tenant, not owner
    RELATIVE_OR_ASSOCIATE       — caller is a relative or associate, not owner
    DO_NOT_CALL                 — caller requested no further contact
    QUARANTINED                 — quarantined until evidence changes

Rules enforced here (never fabricated):
    - A matching phone number alone NEVER equals owner-confirmed.
    - A matching property address alone NEVER equals owner-confirmed.
    - A company contact does NOT automatically equal the property owner.
    - A tenant does NOT equal the owner.
    - A relative does NOT equal the owner.
    - A wrong person can never remain seller-confirmed.
    - An existing verified public record is never overwritten by an
      unsupported caller statement without its own call-level evidence.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]


class IdentityState(str, Enum):
    OWNER_CONFIRMED = "OWNER_CONFIRMED"
    OWNER_LIKELY = "OWNER_LIKELY"
    AUTHORIZED_DECISION_MAKER = "AUTHORIZED_DECISION_MAKER"
    IDENTITY_UNCONFIRMED = "IDENTITY_UNCONFIRMED"
    WRONG_PERSON = "WRONG_PERSON"
    WRONG_NUMBER = "WRONG_NUMBER"
    TENANT = "TENANT"
    RELATIVE_OR_ASSOCIATE = "RELATIVE_OR_ASSOCIATE"
    DO_NOT_CALL = "DO_NOT_CALL"
    QUARANTINED = "QUARANTINED"


class CallerRelationship(str, Enum):
    OWNER = "OWNER"
    AUTHORIZED_DECISION_MAKER = "AUTHORIZED_DECISION_MAKER"
    TENANT = "TENANT"
    RELATIVE_OR_ASSOCIATE = "RELATIVE_OR_ASSOCIATE"
    UNKNOWN = "UNKNOWN"
    WRONG_PERSON = "WRONG_PERSON"


# States that must NEVER surface as primary seller calls.
SUPPRESSED_FROM_PRIMARY = {
    IdentityState.WRONG_PERSON,
    IdentityState.WRONG_NUMBER,
    IdentityState.TENANT,
    IdentityState.RELATIVE_OR_ASSOCIATE,
    IdentityState.DO_NOT_CALL,
    IdentityState.QUARANTINED,
}

# Score components (only evidence-backed).
SCORE_NAME_MATCH = 40      # verified owner name matches caller-confirmed name
SCORE_PROPERTY = 30        # property identity confirmed by caller
SCORE_AUTHORITATIVE = 20   # authoritative ownership evidence (parcel/DCAD)
SCORE_RELATIONSHIP = 10    # existing verified contact relationship
SCORE_MAX = SCORE_NAME_MATCH + SCORE_PROPERTY + SCORE_AUTHORITATIVE + SCORE_RELATIONSHIP


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z ]", "", (name or "").lower()).strip()


def _normalize_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", str(phone or ""))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    return digits


def names_match(db_name: str, caller_name: str) -> bool:
    """Fuzzy first/last token match between a verified record name and the
    name the caller gives over the phone. Requires at least a surname overlap."""
    a = _normalize_name(db_name)
    b = _normalize_name(caller_name)
    if not a or not b:
        return False
    a_tokens = set(a.split())
    b_tokens = set(b.split())
    # A surname (last token) match on either side is the minimum bar.
    a_last = a.split()[-1]
    b_last = b.split()[-1]
    if a_last == b_last:
        return True
    shared = a_tokens & b_tokens
    return len(shared) >= 2 or (a_last in b_tokens or b_last in a_tokens)


def _get_owner_name(lead: dict) -> str:
    details = lead.get("details") or {}
    for key in ("owner_name", "Owner_Name", "contact", "name", "prospect_name"):
        v = lead.get(key) or details.get(key)
        if v and str(v).strip():
            return str(v).strip()
    return ""


def _get_property_identity(lead: dict) -> str:
    details = lead.get("details") or {}
    for key in ("property_address", "address", "company", "property"):
        v = lead.get(key) or details.get(key)
        if v and str(v).strip():
            return str(v).strip()
    return ""


def _has_authoritative_ownership_evidence(lead: dict) -> bool:
    """Authoritative ownership evidence = a name + property identity pair from
    a public record (parcel/APN/address), NOT merely a phone beside an address."""
    owner = _get_owner_name(lead)
    prop = _get_property_identity(lead)
    if not owner or not prop:
        return False
    details = lead.get("details") or {}
    source = str(details.get("source") or lead.get("source") or "").upper()
    source_class = str(lead.get("source_class") or "").upper()
    has_parcel = bool(details.get("parcel_id") or details.get("parcel"))
    county_ev = (
        "COUNTY" in source
        or "DCAD" in source
        or "APPRAISAL" in source
        or source_class == "COUNTY_RECORD"
        or "PARCEL" in source
        or has_parcel
    )
    verified_flag = (
        lead.get("owner_status") in ("VERIFIED_OWNER", "VERIFIED_DECISION_MAKER")
        or (details.get("Owner_Status") in ("VERIFIED_OWNER", "VERIFIED_DECISION_MAKER"))
    )
    return county_ev and verified_flag


def _has_existing_verified_relationship(lead: dict) -> bool:
    st = str(lead.get("skip_trace_status") or "").upper()
    conf = str(lead.get("contact_confidence") or "").upper()
    return st == "VERIFIED" and conf in ("HIGH", "MEDIUM")


@dataclass
class IdentityResult:
    lead_id: str
    state: IdentityState
    score: int
    score_breakdown: dict = field(default_factory=dict)
    relationship: str = ""
    property_confirmed: bool = False
    name_confirmed: bool = False
    caller_name: str = ""
    evidence_used: list = field(default_factory=list)
    created_at: str = field(default_factory=_iso_now)
    source: str = "CALL_LEVEL"
    verification_source: str = "CALLER_CONFIRMATION"
    previous_identity_state: str = ""

    def to_dict(self) -> dict:
        d = dict(self.__dict__)
        d["state"] = self.state.value if isinstance(self.state, IdentityState) else str(self.state)
        return d


def score_owner_match(lead: dict, *, caller_name: str = "", relationship: str = "",
                      property_confirmed: bool = False, name_confirmed: bool = False) -> dict:
    """Compute a transparent identity score using only available evidence.

    Returns {'score', 'breakdown', 'evidence'} — NEVER fabricates certainty.
    The caller's confirmation of the name/property relationship is required to
    reach OWNER_CONFIRMED; database evidence alone caps at OWNER_LIKELY.
    """
    score = 0
    breakdown = {}
    evidence = []

    db_owner = _get_owner_name(lead)
    db_prop = _get_property_identity(lead)
    authoritative = _has_authoritative_ownership_evidence(lead)
    relationship_ev = _has_existing_verified_relationship(lead)

    # +40: verified owner name matches caller-confirmed name
    name_matched = name_confirmed and bool(caller_name) and names_match(db_owner, caller_name)
    if name_matched:
        score += SCORE_NAME_MATCH
        breakdown["name_match"] = SCORE_NAME_MATCH
        evidence.append(f"verified owner name '{db_owner}' matches caller-confirmed name '{caller_name}'")

    # +30: property identity confirmed
    if property_confirmed and db_prop:
        score += SCORE_PROPERTY
        breakdown["property_confirmed"] = SCORE_PROPERTY
        evidence.append(f"caller confirmed property identity '{db_prop}'")

    # +20: authoritative ownership evidence (parcel/DCAD name+property pair)
    if authoritative:
        score += SCORE_AUTHORITATIVE
        breakdown["authoritative_evidence"] = SCORE_AUTHORITATIVE
        evidence.append("authoritative ownership record (DCAD/county parcel)")

    # +10: existing verified contact relationship
    if relationship_ev:
        score += SCORE_RELATIONSHIP
        breakdown["existing_relationship"] = SCORE_RELATIONSHIP
        evidence.append("existing verified contact relationship")

    # The score can never manufacture certainty: without a caller-confirmed
    # name matching the record, an authoritative record alone caps at 60.
    return {"score": min(score, SCORE_MAX), "breakdown": breakdown, "evidence": evidence,
            "authoritative": authoritative, "name_matched": name_matched,
            "db_owner": db_owner, "db_prop": db_prop}


def classify_identity(score: int, *, caller_name: str = "", relationship: str = "",
                      property_confirmed: bool = False, name_confirmed: bool = False,
                      authoritative: bool = False) -> tuple[IdentityState, str]:
    """Classify an identity state from a score + caller-supplied relationship.

    Relationship is the strongest signal for negative states; score governs
    positive/uncertain states. Never promotes an unconfirmed person to
    OWNER_CONFIRMED, and never demotes a verified record to WRONG_PERSON
    without the caller explicitly claiming a non-owner relationship.

    OWNER_CONFIRMED requires THREE explicit call-level facts:
      1. the caller identifies themselves as the OWNER (relationship=OWNER), and
      2. the caller confirms their name matches the verified record, and
      3. the caller confirms the property relationship (property_confirmed).
    It is NEVER derived from phone match, DB record, address match, caller
    assumption, or AI inference alone.

    AUTHORIZED_DECISION_MAKER stays SEPARATE from OWNER_CONFIRMED: when the
    caller explicitly establishes they are authorized to make decisions for
    the property owner, that is its own state — it is never collapsed into
    OWNER_CONFIRMED and never demoted by an incomplete name capture.
    """
    rel = (relationship or "").upper()
    if rel in ("WRONG_PERSON",):
        return IdentityState.WRONG_PERSON, "caller identified as wrong person"
    if rel in ("TENANT",):
        return IdentityState.TENANT, "caller identified as tenant"
    if rel in ("RELATIVE", "RELATIVE_OR_ASSOCIATE"):
        return IdentityState.RELATIVE_OR_ASSOCIATE, "caller identified as relative/associate"

    # Explicitly authorized decision-maker is its own state. Even a strong
    # score/name match on an ADM call does NOT promote them to OWNER.
    if rel == "AUTHORIZED_DECISION_MAKER":
        return IdentityState.AUTHORIZED_DECISION_MAKER, "caller explicitly established authorization to decide for owner"

    if not name_confirmed or not caller_name:
        # No caller name confirmation → cannot be owner-confirmed regardless of score.
        # A database-verified ownership record (authoritative) is OWNER_LIKELY —
        # the record strongly suggests the owner, but who answers is unconfirmed.
        if authoritative or score >= 70:
            return IdentityState.OWNER_LIKELY, "authoritative record, identity not call-confirmed"
        if score >= 40:
            return IdentityState.IDENTITY_UNCONFIRMED, "partial evidence, no caller confirmation"
        return IdentityState.IDENTITY_UNCONFIRMED, "no supporting evidence"

    # OWNER_CONFIRMED requires the caller to identify AS the owner AND confirm
    # both name match and property. A verified record + caller name match but
    # NO property confirmation caps at OWNER_LIKELY (never OWNER_CONFIRMED).
    if rel == "OWNER" and name_confirmed and property_confirmed and score >= 90:
        return IdentityState.OWNER_CONFIRMED, "caller identifies as owner; name matches verified record; property confirmed"
    if score >= 70:
        return IdentityState.OWNER_LIKELY, "strong evidence, still not fully call-confirmed"
    if score >= 40:
        return IdentityState.IDENTITY_UNCONFIRMED, "partial identity evidence"
    return IdentityState.IDENTITY_UNCONFIRMED, "insufficient evidence"


def evaluate_lead_identity(lead: dict, *, caller_name: str = "", relationship: str = "",
                           property_confirmed: bool = False, name_confirmed: bool = False,
                           wrong_number: bool = False, do_not_call: bool = False) -> IdentityResult:
    """Full identity evaluation for a lead + call-level caller input."""
    lead_id = str(lead.get("id") or lead.get("lead_id") or "")
    prev = lead.get("identity_state") or (lead.get("details") or {}).get("identity_state", "")
    if wrong_number:
        return IdentityResult(lead_id=lead_id, state=IdentityState.WRONG_NUMBER,
                              score=0, relationship="WRONG_NUMBER",
                              evidence_used=["caller reported wrong number"],
                              previous_identity_state=prev)
    if do_not_call:
        return IdentityResult(lead_id=lead_id, state=IdentityState.DO_NOT_CALL,
                              score=0, relationship="DO_NOT_CALL",
                              evidence_used=["caller requested no further contact"],
                              previous_identity_state=prev)

    scored = score_owner_match(
        lead, caller_name=caller_name, relationship=relationship,
        property_confirmed=property_confirmed, name_confirmed=name_confirmed,
    )
    state, reason = classify_identity(
        scored["score"], caller_name=caller_name, relationship=relationship,
        property_confirmed=property_confirmed, name_confirmed=name_confirmed,
        authoritative=scored["authoritative"],
    )
    return IdentityResult(
        lead_id=lead_id, state=state, score=scored["score"],
        score_breakdown=scored["breakdown"], relationship=(relationship or "").upper(),
        property_confirmed=bool(property_confirmed), name_confirmed=bool(name_confirmed),
        caller_name=caller_name, evidence_used=scored["evidence"] + [reason],
        previous_identity_state=prev,
    )


def is_primary_eligible(state: str | IdentityState) -> bool:
    """Primary seller queue protection: suppressed states never surface as
    primary seller calls."""
    if isinstance(state, str):
        try:
            state = IdentityState(state)
        except ValueError:
            return True
    return state not in SUPPRESSED_FROM_PRIMARY


# Identity-state queue priority (lower = called first). After a live call:
#   OWNER_CONFIRMED             → highest seller confidence
#   AUTHORIZED_DECISION_MAKER   → high seller confidence
#   OWNER_LIKELY                → callable, visibly unconfirmed
#   IDENTITY_UNCONFIRMED        → lower priority
#   suppressed states          → never in the primary queue
IDENTITY_QUEUE_PRIORITY: dict[str, int] = {
    "OWNER_CONFIRMED": 0,
    "AUTHORIZED_DECISION_MAKER": 1,
    "OWNER_LIKELY": 2,
    "IDENTITY_UNCONFIRMED": 3,
    "WRONG_PERSON": 100,
    "WRONG_NUMBER": 100,
    "TENANT": 100,
    "RELATIVE_OR_ASSOCIATE": 100,
    "DO_NOT_CALL": 100,
    "QUARANTINED": 100,
}


def identity_queue_rank(lead: dict) -> int:
    """Rank a lead for the seller queue by its identity state. Lower rank is
    called first. A lead with no recorded identity state is treated as
    callable-but-unconfirmed (rank 2) so an unverified record never jumps the
    queue ahead of a live-confirmed owner."""
    raw = lead.get("identity_state")
    if not raw:
        raw = (lead.get("details") or {}).get("identity_state", "")
    if raw in IDENTITY_QUEUE_PRIORITY:
        return IDENTITY_QUEUE_PRIORITY[raw]
    return 2


def apply_identity_to_lead(lead: dict, result: IdentityResult) -> dict:
    """Stamp identity state onto a lead WITHOUT destroying any existing sales
    data (dispositions, notes, attempts, last_touch, stage, property, source)."""
    lead = dict(lead)
    lead["identity_state"] = result.state.value if isinstance(result.state, IdentityState) else str(result.state)
    lead["identity_score"] = result.score
    lead["identity_relationship"] = result.relationship
    lead["identity_property_confirmed"] = bool(result.property_confirmed)
    lead["identity_name_confirmed"] = bool(result.name_confirmed)
    lead["identity_caller_name"] = result.caller_name
    lead["identity_evidence"] = result.evidence_used
    lead["identity_updated_at"] = result.created_at
    lead["caller_identity_verified"] = result.state in (IdentityState.OWNER_CONFIRMED,
                                                        IdentityState.AUTHORIZED_DECISION_MAKER)
    # Preserve database-level ownership verification marker separately.
    lead["database_ownership_verified"] = _has_authoritative_ownership_evidence(lead)
    return lead


# ── Persistence ────────────────────────────────────────────────────────

IDENTITY_RESULTS_FILE = ROOT_DIR / "MBM" / "LeadEngine" / "logs" / "call_identity_results.json"


def load_identity_results() -> list[dict]:
    if not IDENTITY_RESULTS_FILE.exists():
        return []
    try:
        data = json.loads(IDENTITY_RESULTS_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def save_identity_result(result: IdentityResult | dict, *, previous_state: str = "") -> dict:
    """Append an identity result to the persistent log (idempotent per lead).

    Duplicate submissions for the same lead replace the previous record rather
    than stacking. The previous identity state is captured so the state-machine
    transitions are auditable (e.g. OWNER_LIKELY → OWNER_CONFIRMED).
    """
    results = load_identity_results()
    rec = result.to_dict() if isinstance(result, IdentityResult) else dict(result)
    if not rec.get("lead_id"):
        raise ValueError("identity result requires lead_id")
    # Canonical field name is identity_state (the same key stamped on leads).
    if "identity_state" not in rec and rec.get("state"):
        rec["identity_state"] = rec["state"]
    # Capture the previous state from the LAST RECORDED result (authoritative)
    # on repeats; otherwise use the caller-provided/lead-derived previous state.
    existing = [r for r in results if r.get("lead_id") == rec.get("lead_id")]
    if existing:
        rec["previous_identity_state"] = existing[-1].get("identity_state", "")
        results = [r for r in results if r.get("lead_id") != rec.get("lead_id")]
    else:
        rec.setdefault("previous_identity_state", previous_state)
    rec.setdefault("verification_source", "CALLER_CONFIRMATION")
    rec.setdefault("source", "CALL_LEVEL")
    results.append(rec)
    IDENTITY_RESULTS_FILE.write_text(json.dumps(results, indent=2), encoding="utf-8")
    return rec


def stamp_identity_into_dialer_db(result: IdentityResult | dict, db_path: Path | None = None) -> int:
    """Patch identity state onto the matching lead in leads_database.json while
    preserving all other fields. Returns number of patched leads."""
    db_path = db_path or (ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json")
    rec = result.to_dict() if isinstance(result, IdentityResult) else dict(result)
    state = rec.get("identity_state") or rec.get("state") or ""
    if not db_path.exists():
        return 0
    data = json.loads(db_path.read_text(encoding="utf-8"))
    arr = data if isinstance(data, list) else data.get("leads", [])
    patched = 0
    for lead in arr:
        if str(lead.get("id")) == str(rec.get("lead_id")):
            lead["identity_state"] = state
            lead["identity_score"] = rec.get("score", 0)
            lead["identity_relationship"] = rec.get("relationship", "")
            lead["identity_property_confirmed"] = bool(rec.get("property_confirmed"))
            lead["identity_name_confirmed"] = bool(rec.get("name_confirmed"))
            lead["identity_caller_name"] = rec.get("caller_name", "")
            lead["identity_evidence"] = rec.get("evidence_used", [])
            lead["identity_updated_at"] = rec.get("created_at") or rec.get("timestamp") or _iso_now()
            lead["caller_identity_verified"] = state in (
                IdentityState.OWNER_CONFIRMED.value, IdentityState.AUTHORIZED_DECISION_MAKER.value)
            lead["database_ownership_verified"] = _has_authoritative_ownership_evidence(lead)
            patched += 1
    if patched:
        if isinstance(data, list):
            db_path.write_text(json.dumps(arr, indent=2), encoding="utf-8")
        else:
            data["leads"] = arr
            db_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return patched


def audit_identity(leads: list[dict]) -> dict:
    """Classify every lead by its current identity state (database-level, no
    caller input — so nothing is ever OWNER_CONFIRMED without call evidence)."""
    counts = {state.value: 0 for state in IdentityState}
    db_verified = 0
    caller_verified = 0
    unknown = 0
    for lead in leads:
        state = lead.get("identity_state")
        if not state:
            db = _has_authoritative_ownership_evidence(lead)
            state = IdentityState.OWNER_LIKELY.value if db else IdentityState.IDENTITY_UNCONFIRMED.value
        if state in counts:
            counts[state] += 1
        if lead.get("caller_identity_verified"):
            caller_verified += 1
        if lead.get("database_ownership_verified") or _has_authoritative_ownership_evidence(lead):
            db_verified += 1
        if state == IdentityState.IDENTITY_UNCONFIRMED.value:
            unknown += 1
    return {
        "top100_total": len(leads),
        "owner_confirmed": counts[IdentityState.OWNER_CONFIRMED.value],
        "owner_likely": counts[IdentityState.OWNER_LIKELY.value],
        "authorized_decision_maker": counts[IdentityState.AUTHORIZED_DECISION_MAKER.value],
        "identity_unconfirmed": counts[IdentityState.IDENTITY_UNCONFIRMED.value],
        "wrong_person": counts[IdentityState.WRONG_PERSON.value],
        "wrong_number": counts[IdentityState.WRONG_NUMBER.value],
        "tenant": counts[IdentityState.TENANT.value],
        "relative_or_associate": counts[IdentityState.RELATIVE_OR_ASSOCIATE.value],
        "do_not_call": counts[IdentityState.DO_NOT_CALL.value],
        "quarantined": counts[IdentityState.QUARANTINED.value],
        "database_ownership_verified": db_verified,
        "caller_identity_verified": caller_verified,
        "identity_unknown": unknown,
    }


if __name__ == "__main__":
    db_path = ROOT_DIR / "mbm-dialer" / "app" / "public" / "leads_database.json"
    if db_path.exists():
        data = json.loads(db_path.read_text(encoding="utf-8"))
        arr = data if isinstance(data, list) else data.get("leads", [])
        report = audit_identity(arr[:100])
        print("=== OWNER IDENTITY AUDIT (TOP 100) ===")
        for k, v in report.items():
            print(f"  {k}: {v}")