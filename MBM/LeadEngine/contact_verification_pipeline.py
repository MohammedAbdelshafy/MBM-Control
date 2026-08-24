"""contact_verification_pipeline -- P0/P1 lead-quality rebuild for the MBM Dialer.

Implements the contact verification state machine, synthetic-phone detection,
multi-source consensus scoring, quarantine ledger, call-feedback handling,
and the seller quality gate.

Design laws:
  - A phone existing is NOT a phone verified. An owner named is NOT an owner
    verified. Callable requires the full chain.
  - History is never destroyed: bad data is QUARANTINED with provenance.
  - Every decision records actor, reason, timestamp (audit events).
  - Scoring weights are configuration, not truth.

Verification chain (Phase-2 model):
    DISCOVERED -> PROPERTY_VERIFIED -> OWNER_VERIFIED -> CONTACT_ENRICHED
    -> CONTACT_CROSSCHECKED -> PHONE_VERIFIED -> COMPLIANCE_CHECKED -> CALLABLE

Failure states: NEEDS_REVIEW, BAD_PHONE, OWNER_MISMATCH, STALE_CONTACT, DNC,
LITIGATOR, SUPPRESSED, SYNTHETIC, MALFORMED, NO_VERIFIED_CONTACT.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# ---------------------------------------------------------------------------
# Verification states (Phase 2)
# ---------------------------------------------------------------------------

CHAIN_STATES = [
    "DISCOVERED",
    "PROPERTY_VERIFIED",
    "OWNER_VERIFIED",
    "CONTACT_FOUND",
    "CONTACT_IDENTITY_VERIFIED",
    "PHONE_FOUND",
    "PHONE_VERIFIED",
    "COMPLIANCE_CLEAR",
    "CALL_READY",
]

FAILURE_STATES = [
    "NEEDS_REVIEW", "NO_VERIFIED_CONTACT", "BAD_PHONE", "DISCONNECTED",
    "WRONG_PARTY", "OWNER_MISMATCH", "STALE_CONTACT", "DNC", "SUPPRESSED",
    "LITIGATOR", "SYNTHETIC", "MALFORMED",
]

# Lead lanes that must never share a callable queue (Phase 8)
LANE_SEGMENTS = {
    "REAL_ESTATE_SELLER": {"segment": "DISTRESSED_SELLER"},
    "AI_BUSINESS_PROSPECT": {"segment": "AI_CONSULTANCY"},
    "HEALTHCARE_PROSPECT": {"segment": "HEALTHCARE_CLINIC"},
    "CONSTRUCTION_PROSPECT": {"segment": "CONTRACTOR"},
    "OTHER_B2B": {"segment": "*other*"},
}

CORPORATE_ENTITY_RE = re.compile(
    r"\b(LLC|L\.L\.C\.|LP|L\.P\.|INC|CORP|TRUST|PARTNERS(HIP)?|HOLDINGS?|REO|"
    r"CAPITAL|PROPERTIES|INVESTMENTS|GROUP|VENTURES|ENTERPRISES)\b",
    re.IGNORECASE,
)


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Phone normalization / validity
# ---------------------------------------------------------------------------

_DIGITS_RE = re.compile(r"\d+")


def normalize_phone(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    digits = "".join(_DIGITS_RE.findall(str(raw)))
    if digits.startswith("1") and len(digits) == 11:
        digits = digits[1:]
    if len(digits) != 10:
        return None
    area, exch = digits[0:3], digits[3:6]
    if area[0] in "01" or exch[0] in "01":
        return None
    return digits


class SyntheticPhoneDetector:
    """Detects phones that pattern-match fabrication rather than telephony."""

    @staticmethod
    def id_derived(lead_id: str, phone_raw: Any) -> bool:
        """True when a meaningful numeric token of the lead id appears inside
        the phone digits.

        Checks EVERY numeric token in the id (>=4 digits), not just the
        trailing run: 'DCAD-TOP50-695130' carries tokens {50, 695130}; a phone
        ending 8695130 is fabrication even though the raw last-7 differs.
        This is the exact failure mode of the 2026-08 contamination.
        """
        phone = normalize_phone(phone_raw)
        if not phone:
            return False
        tokens = [t for t in re.findall(r"\d+", str(lead_id or "")) if len(t) >= 4]
        if not tokens:
            return False
        return any(tok in phone[-10:] for tok in tokens)

    @staticmethod
    def repeated_digits(phone_raw: Any, run: int = 5) -> bool:
        phone = normalize_phone(phone_raw)
        if not phone:
            return False
        return bool(re.search(r"(.)\1{%d,}" % (run - 1), phone))

    @staticmethod
    def reserved_555(phone_raw: Any) -> bool:
        phone = normalize_phone(phone_raw)
        return bool(phone) and phone[3:6] == "555"

    @classmethod
    def classify(cls, lead_id: str, phone_raw: Any) -> Optional[str]:
        """Return SYNTHETIC/MALFORMED/None."""
        phone = normalize_phone(phone_raw)
        if not phone:
            return "MALFORMED"
        if cls.reserved_555(phone) or cls.repeated_digits(phone):
            return "SYNTHETIC"
        if cls.id_derived(lead_id, phone_raw):
            return "SYNTHETIC"
        return None


# ---------------------------------------------------------------------------
# Consensus scoring (Phase 4) -- configurable, documented, not truth
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS = {
    "OWNER_MATCH": 30,
    "ADDRESS_MATCH": 20,
    "MULTI_SOURCE_MATCH": 20,
    "RECENCY": 10,
    "PHONE_TYPE_MOBILE": 10,
    "SOURCE_RELIABILITY": 10,
}
DEFAULT_THRESHOLDS = {"HIGH": 90, "REVIEW_POLICY": 75, "NEEDS_REVIEW": 60}


@dataclass
class PhoneCandidate:
    phone: str                    # normalized 10-digit
    owner_match: float = 0.0      # 0..1 evidence that phone belongs to owner
    address_match: float = 0.0    # 0..1 property/address linkage
    sources: list[str] = field(default_factory=list)
    line_type: str = ""           # mobile | landline | voip | unknown
    last_verified_at: str = ""
    source_reliability: float = 0.5   # 0..1 per-provider reliability
    dnc: bool = False
    litigator: bool = False
    suppressed: bool = False


@dataclass
class ConsensusConfig:
    weights: dict = field(default_factory=lambda: dict(DEFAULT_WEIGHTS))
    thresholds: dict = field(default_factory=lambda: dict(DEFAULT_THRESHOLDS))
    recency_days_full: int = 30


class PhoneConsensusEngine:
    """Scores and ranks phone candidates for ONE lead. Configurable only."""

    def __init__(self, config: ConsensusConfig | None = None):
        self.cfg = config or ConsensusConfig()

    def _recency_score(self, last_verified_at: str) -> float:
        if not last_verified_at:
            return 0.0
        try:
            dt = datetime.fromisoformat(str(last_verified_at).replace("Z", "+00:00"))
        except ValueError:
            return 0.0
        days = max((datetime.now(timezone.utc) - dt).days, 0)
        window = max(self.cfg.recency_days_full, 1)
        return max(0.0, 1.0 - days / window)

    def score_candidate(self, cand: PhoneCandidate) -> dict:
        w = self.cfg.weights
        if cand.dnc or cand.suppressed or cand.litigator:
            return {
                "phone": cand.phone, "score": 0, "tier": "DO_NOT_CALL",
                "compliance_block": True,
                "breakdown": {},
                "reasons": ["DNC/suppression/litigator flag overrides any score"],
            }
        breakdown = {
            "OWNER_MATCH": round(w["OWNER_MATCH"] * min(max(cand.owner_match, 0.0), 1.0), 1),
            "ADDRESS_MATCH": round(w["ADDRESS_MATCH"] * min(max(cand.address_match, 0.0), 1.0), 1),
            "MULTI_SOURCE_MATCH": round(
                w["MULTI_SOURCE_MATCH"] * (min(len(set(cand.sources)), 2) / 2), 1),
            "RECENCY": round(w["RECENCY"] * self._recency_score(cand.last_verified_at), 1),
            "PHONE_TYPE_MOBILE": round(
                w["PHONE_TYPE_MOBILE"] * (1.0 if cand.line_type.lower() == "mobile" else 0.3), 1),
            "SOURCE_RELIABILITY": round(
                w["SOURCE_RELIABILITY"] * min(max(cand.source_reliability, 0.0), 1.0), 1),
        }
        total = round(sum(breakdown.values()), 1)
        t = self.cfg.thresholds
        if total >= t["HIGH"]:
            tier = "HIGH_CONFIDENCE_CALLABLE"
        elif total >= t["REVIEW_POLICY"]:
            tier = "CALLABLE_WITH_REVIEW_POLICY"
        elif total >= t["NEEDS_REVIEW"]:
            tier = "NEEDS_REVIEW"
        else:
            tier = "DO_NOT_CALL"
        return {"phone": cand.phone, "score": total, "tier": tier,
                "breakdown": breakdown, "compliance_block": False}

    def rank(self, candidates: list[PhoneCandidate]) -> list[dict]:
        ranked = [self.score_candidate(c) for c in candidates]
        ranked.sort(key=lambda r: (-r["score"], r["phone"]))
        return ranked


# ---------------------------------------------------------------------------
# Quarantine ledger (Phase 5)
# ---------------------------------------------------------------------------

PHONE_STATUS_VALUES = {
    "VERIFIED", "UNVERIFIED", "BAD", "DISCONNECTED", "OWNER_MISMATCH",
    "DNC", "SUPPRESSED", "NEEDS_RECHECK", "SYNTHETIC_ID_DERIVED",
    "MALFORMED", "CATEGORY_MISMATCH",
}


class QuarantineLedger:
    """Append-only JSONL quarantine/history store. Never deletes."""

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def add(self, *, lead_id: str, company: str, phone: str, phone_status: str,
            reason_code: str, detail: str = "", previous_callable: bool = False,
            actor: str = "OX-ENGINEERING") -> dict:
        assert phone_status in PHONE_STATUS_VALUES, f"bad status {phone_status}"
        event = {
            "event_id": hashlib.sha256(
                f"{lead_id}|{phone}|{phone_status}|{_iso_now()}".encode()
            ).hexdigest()[:16],
            "ts": _iso_now(),
            "lead_id": lead_id,
            "company": company,
            "phone": phone,
            "phone_status": phone_status,
            "reason_code": reason_code,
            "detail": detail[:300],
            "previous_callable": previous_callable,
            "actor": actor,
        }
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event

    def known_bad_phones(self) -> set[str]:
        bad: set[str] = set()
        if not self.path.exists():
            return bad
        for line in self.path.read_text(encoding="utf-8").splitlines():
            try:
                e = json.loads(line)
                if e.get("phone") and e.get("phone_status") not in ("VERIFIED", "UNVERIFIED"):
                    bad.add(re.sub(r"\D", "", e["phone"])[-10:])
            except json.JSONDecodeError:
                continue
        return bad


# ---------------------------------------------------------------------------
# Call feedback loop (Phase 6)
# ---------------------------------------------------------------------------

CALL_OUTCOMES = {
    "BAD_NUMBER", "CONNECTED_OWNER", "WRONG_PERSON", "WRONG_NUMBER",
    "DISCONNECTED", "VOICEMAIL", "NO_ANSWER", "DO_NOT_CALL", "INTERESTED",
    "NOT_INTERESTED", "CALLBACK", "APPOINTMENT", "QUALIFIED", "UNQUALIFIED",
    "WRONG_PARTY",
}
BAD_PHONE_OUTCOMES = {"BAD_NUMBER", "WRONG_NUMBER", "DISCONNECTED"}
DNC_OUTCOMES = {"DO_NOT_CALL"}
IDENTITY_OUTCOMES = {"WRONG_PERSON", "WRONG_PARTY"}
STATUS_FOR_OUTCOME = {
    "BAD_NUMBER": "BAD",
    "WRONG_NUMBER": "BAD",
    "DISCONNECTED": "DISCONNECTED",
    "DO_NOT_CALL": "DNC",
    "WRONG_PERSON": "OWNER_MISMATCH",
    "WRONG_PARTY": "WRONG_PARTY",
}


@dataclass
class CallFeedbackResult:
    lead_id: str
    outcome: str
    phone_status: str | None
    remove_from_callable: bool
    trigger_reverify: bool
    audit_event: dict


def handle_call_feedback(
    lead: dict,
    outcome: str,
    actor: str = "rep",
    note: str = "",
    next_phone: Any = None,
) -> CallFeedbackResult:
    """Apply one rep/system call outcome to a lead dict IN PLACE and return
    the resulting actions. The caller persists via the canonical writer."""
    assert outcome in CALL_OUTCOMES, f"unknown outcome {outcome}"
    ts = _iso_now()
    lead.setdefault("call_history", [])
    audit_event = {
        "event": "CALL_FEEDBACK",
        "outcome": outcome,
        "actor": actor,
        "ts": ts,
        "note": note[:200],
    }
    lead["call_history"].append(audit_event)
    lead["last_call_result"] = outcome
    lead["last_call_at"] = ts

    remove_from_callable = False
    trigger_reverify = False
    phone_status: str | None = None

    if outcome in BAD_PHONE_OUTCOMES:
        phone_status = STATUS_FOR_OUTCOME[outcome]
        old = lead.get("phone")
        lead.setdefault("quarantined_phones", []).append(
            {"phone": old, "status": phone_status, "ts": ts, "outcome": outcome})
        lead["phone_status"] = phone_status
        if next_phone:
            lead["phone"] = next_phone
            lead["phone_verified"] = False
            lead["verification_status"] = "UNVERIFIED"
            trigger_reverify = True
        else:
            lead["callable"] = False
            lead["is_callable"] = False
            lead["queue_bucket"] = "QUARANTINED_BAD_NUMBER"
            lead["next_action"] = "REVERIFY_CONTACT"
        remove_from_callable = not bool(next_phone)
        trigger_reverify = True
        lead["confidence"] = max(0, int(lead.get("confidence") or lead.get("callability_score") or 50) - 25)
    elif outcome in DNC_OUTCOMES:
        phone_status = "DNC"
        lead["callable"] = False
        lead["is_callable"] = False
        lead["suppression_reason"] = "REP_REPORTED_DNC"
        lead["queue_bucket"] = "SUPPRESSED"
        remove_from_callable = True
    elif outcome in ("WRONG_PERSON", "WRONG_PARTY"):
        phone_status = STATUS_FOR_OUTCOME[outcome]
        lead["owner_match_status"] = "MISMATCH_REPORTED"
        lead["queue_bucket"] = "NEEDS_REVIEW_OWNER_MISMATCH"
        lead["callable"] = False
        lead["is_callable"] = False
        remove_from_callable = True

    lead["updated_at"] = ts
    return CallFeedbackResult(
        lead_id=str(lead.get("id")), outcome=outcome, phone_status=phone_status,
        remove_from_callable=remove_from_callable, trigger_reverify=trigger_reverify,
        audit_event=audit_event,
    )


# ---------------------------------------------------------------------------
# Seller quality gate (Phase 8)
# ---------------------------------------------------------------------------

SELLER_REQUIRED_EVIDENCE = (
    "valid_property", "verified_owner", "ownership_relationship",
    "property_address", "contact_path", "compliance_clear", "provenance",
)


def seller_quality_gate(lead: dict) -> tuple[bool, str]:
    """SELLER lane admission v2 -- identity-first.

    Hard rules:
      - synthetic/id-derived/malformed phone -> SYNTHETIC/MALFORMED
      - healthcare-registry sourcing in the seller lane -> CATEGORY_MISMATCH
      - institutional/corporate contacts -> NEEDS_REVIEW (weak seller fit)
      - county-parcel verification alone proves PROPERTY/OWNER identity but
        NOT that a phone belongs to that owner. CALL_READY additionally
        requires an explicit owner<->phone evidence link:
            details.owner_phone_evidence in {TITLED_OWNER_DIRECT,
            AUTHORIZED_REPRESENTATIVE, MULTI_SOURCE_IDENTITY_AGREEMENT}
        Absent that link the record is NEEDS_REVIEW (NO_VERIFIED_CONTACT),
        never callable.
    """
    lead_id = str(lead.get("id"))
    verdict = SyntheticPhoneDetector.classify(lead_id, lead.get("phone"))
    if verdict == "MALFORMED":
        return False, "MALFORMED"
    if verdict == "SYNTHETIC":
        return False, "SYNTHETIC"

    src = f"{lead.get('skip_trace_source','')} {lead.get('source','')}".lower()
    if "npi" in src or "cms" in src or "healthcare" in src:
        return False, "CATEGORY_MISMATCH"

    if str(lead.get("owner_status")) != "VERIFIED_OWNER":
        return False, "NEEDS_REVIEW"

    method = str(lead.get("verification_method") or "")
    if "DCAD_OFFICIAL_TAX_ROLL_PARCEL_VERIFIED" not in method:
        return False, "STALE_CONTACT"

    contact = f"{lead.get('contact','')} {lead.get('company','')}"
    if CORPORATE_ENTITY_RE.search(contact):
        return False, "NEEDS_REVIEW"

    details = lead.get("details") or {}
    evidence = str(details.get("owner_phone_evidence") or "").upper()
    if evidence not in ("TITLED_OWNER_DIRECT", "AUTHORIZED_REPRESENTATIVE",
                        "MULTI_SOURCE_IDENTITY_AGREEMENT"):
        return False, "NEEDS_REVIEW"

    return True, "CALLABLE"


# ---------------------------------------------------------------------------
# Whole-database audit (Phase 7)
# ---------------------------------------------------------------------------

def audit_database(db: list[dict], quarantine: QuarantineLedger) -> dict:
    known_bad = quarantine.known_bad_phones()
    report: dict[str, Any] = {
        "generated_at": _iso_now(),
        "total_leads": len(db),
        "by_segment": {},
        "total_callable": 0,
        "verified_phone_count": 0,
        "unverified_phone_count": 0,
        "bad_phone_count": 0,
        "owner_mismatch_count": 0,
        "dnc_count": 0,
        "suppressed_count": 0,
        "needs_review_count": 0,
        "synthetic_phone_count": 0,
        "malformed_phone_count": 0,
        "multi_source_match_rate": 0.0,
        "seller_gate": {"admitted": 0, "blocked_by_reason": {}},
        "phone_confidence_distribution": {"HIGH_CONFIDENCE_CALLABLE": 0},
        "contamination_classes": {},
    }
    seg = report["by_segment"]
    contamination: dict[str, int] = {}
    multi_source_hits = 0
    phones_with_source = 0

    for lead in db:
        s = lead.get("segment") or "UNKNOWN"
        seg[s] = seg.get(s, 0) + 1
        if lead.get("callable") in (True, "True"):
            report["total_callable"] += 1
        pv = lead.get("phone_verified") in (True, "True")
        if pv:
            report["verified_phone_count"] += 1
        else:
            report["unverified_phone_count"] += 1

        verdict = SyntheticPhoneDetector.classify(str(lead.get("id")), lead.get("phone"))
        digits = normalize_phone(lead.get("phone"))
        key10 = digits or ""
        if key10 and key10 in known_bad:
            report["bad_phone_count"] += 1
        if verdict == "SYNTHETIC":
            report["synthetic_phone_count"] += 1
            contamination["SYNTHETIC_ID_DERIVED_OR_PATTERN"] = contamination.get("SYNTHETIC_ID_DERIVED_OR_PATTERN", 0) + 1
        elif verdict == "MALFORMED":
            report["malformed_phone_count"] += 1
            contamination["MALFORMED"] = contamination.get("MALFORMED", 0) + 1
        if str(lead.get("suppression_reason") or "").strip():
            report["suppressed_count"] += 1
        if str(lead.get("owner_match_status") or "").strip():
            report["owner_mismatch_count"] += 1

        psrc = str(lead.get("phone_source") or lead.get("skip_trace_source") or "")
        if psrc.strip():
            phones_with_source += 1
            low = psrc.lower()
            if sum(k in low for k in ("registry", "site", "dcad", "county", "nppes")) >= 2:
                multi_source_hits += 1

        if s == "DISTRESSED_SELLER":
            admitted, state = seller_quality_gate(lead)
            if admitted:
                report["seller_gate"]["admitted"] += 1
            else:
                reasons = report["seller_gate"]["blocked_by_reason"]
                reasons[state] = reasons.get(state, 0) + 1

    report["multi_source_match_rate"] = (
        round(multi_source_hits / phones_with_source, 4) if phones_with_source else 0.0
    )
    report["contamination_classes"] = contamination
    report["real_contact_rate_inputs"] = {
        "note": "REAL_CONTACT_RATE = connected_owner / dialed; populated from telemetry as calls accrue",
        "verified_owner_share": round(report["verified_phone_count"] / len(db), 4) if db else 0.0,
    }
    return report


# ---------------------------------------------------------------------------
# Phone quality events (v2, section 9) + provider scoreboard (section 10)
# ---------------------------------------------------------------------------

class PhoneQualityEvents:
    """Append-only event ledger for phone-quality actions."""

    REQUIRED = ("lead_id", "phone", "event_type", "source", "timestamp",
                "provider", "previous_status", "new_status")

    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def record(self, *, lead_id: str, phone: str, event_type: str, source: str,
               rep_id: str = "", provider: str = "", previous_status: str = "",
               new_status: str = "", notes: str = "", timestamp: str = "") -> dict:
        event = {
            "lead_id": lead_id, "phone": phone, "event_type": event_type,
            "source": source, "timestamp": timestamp or _iso_now(), "rep_id": rep_id,
            "provider": provider or "unknown", "previous_status": previous_status,
            "new_status": new_status, "notes": notes[:300],
        }
        missing = [k for k in self.REQUIRED if not str(event.get(k, "")).strip()]
        if missing:
            raise ValueError(f"event missing required fields: {missing}")
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
        return event


class ProviderScoreboard:
    """Measured provider performance. Only REAL call outcomes update it;
    nothing is fabricated or projected."""

    FIELDS = ("calls_attempted", "correct_contacts", "wrong_numbers",
              "wrong_parties", "disconnected", "dnc", "appointments")

    def __init__(self, path: Path):
        self.path = Path(path)
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.data = {}

    def ensure(self, provider: str) -> dict:
        row = self.data.setdefault(provider, {f: 0 for f in self.FIELDS})
        return row

    def record_outcome(self, provider: str, outcome: str) -> dict:
        row = self.ensure(provider)
        row["calls_attempted"] += 1
        mapping = {
            "CONNECTED_OWNER": "correct_contacts", "WRONG_NUMBER": "wrong_numbers",
            "BAD_NUMBER": "wrong_numbers", "WRONG_PARTY": "wrong_parties",
            "DISCONNECTED": "disconnected", "DO_NOT_CALL": "dnc",
            "APPOINTMENT": "appointments",
        }
        key = mapping.get(outcome)
        if outcome == "APPOINTMENT":
            row["correct_contacts"] += 1
        elif outcome == "INTERESTED" or outcome == "QUALIFIED":
            row["correct_contacts"] += 1
        if key:
            row[key] += 1
        self.save()
        return row

    def real_contact_rate(self, provider: str) -> float | None:
        row = self.data.get(provider)
        if not row or not row["calls_attempted"]:
            return None
        return round(row["correct_contacts"] / row["calls_attempted"], 4)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2), encoding="utf-8")


# ---------------------------------------------------------------------------
# Consensus v2 additions: identity match + provider disagreement handling
# ---------------------------------------------------------------------------

def score_candidates_with_identity(
    candidates: list[PhoneCandidate],
    engine: PhoneConsensusEngine | None = None,
    owner_name: str = "",
    property_address: str = "",
    mailing_address: str = "",
) -> list[dict]:
    """Rank candidates; enforce NEEDS_REVIEW on provider disagreement and on
    absent identity linkage. Returns ranked dicts with evidence fields."""
    eng = engine or PhoneConsensusEngine()
    ranked = [dict(eng.score_candidate(c),
                   provider_agreement=sorted(set(c.sources)),
                   line_type=c.line_type,
                   last_verified_at=c.last_verified_at)
              for c in candidates]
    for r, c in zip(ranked, candidates):
        agree = len(set(c.sources)) >= 2
        identity_link = (
            bool(owner_name) and bool(property_address)
            and c.owner_match >= 0.5 and c.address_match >= 0.5
        )
        r["identity_match"] = bool(identity_link)
        if not agree and len({c.source_reliability}) == 1 and not identity_link:
            pass
        if ranked and not identity_link:
            r["tier"] = "NEEDS_REVIEW"
            r["reasons"] = r.get("reasons", []) + ["no proven owner<->phone identity link"]
        if len(set(c.sources)) < 2 and any(
            other.phone == c.phone and set(other.sources) != set(c.sources)
            for other in candidates
        ):
            r["tier"] = "NEEDS_REVIEW"
            r["reasons"] = r.get("reasons", []) + ["provider disagreement on sourcing"]
    ranked.sort(key=lambda r: (-r["score"], r["phone"]))
    return ranked


SCRIPT_SEGMENT_PREFIXES = {
    "REAL_ESTATE_SELLER": "DISTRESSED_SELLER",
    "DISTRESSED_SELLER": "DISTRESSED_SELLER",
    "HEALTHCARE_CLINIC": "HEALTHCARE_CLINIC",
    "AI_CONSULTANCY": "AI_CONSULTANCY",
    "CONTRACTOR": "CONTRACTOR",
}


def script_integrity_check(lead: dict) -> tuple[bool, str]:
    """Every CALL_READY lead must carry a segment-matched script."""
    seg = lead.get("segment")
    if not seg:
        return False, "SEGMENT_MISSING"
    script_id = str(lead.get("script_id") or "")
    if not script_id:
        return False, "SCRIPT_ID_MISSING"
    expected = f"SCRIPT-{seg}-"
    if not script_id.startswith(expected) and seg in SCRIPT_SEGMENT_PREFIXES:
        return False, f"SCRIPT_SEGMENT_MISMATCH:{script_id[:40]}"
    if not str(lead.get("Call_Script") or "").strip():
        return False, "CALL_SCRIPT_EMPTY"
    return True, ""
