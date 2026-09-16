"""GTM guarded actions — deterministic, evidence-only, never autonomous.

Small composable primitives that the GTM convergence layer routes to.
Every function is pure/deterministic (no network, no writes, no sends):

- response_classifier ........ inbound text -> INTERESTED/QUESTION/OBJECTION/
                                NOT_NOW/NOT_A_FIT/UNSUBSCRIBE/UNKNOWN
- score_account ................ transparent multi-factor prospect score
- draft_outreach ............... evidence-interpolated draft; banned claims
                                (ROI/testimonials/guarantees/stats) fail closed
- build_sales_brief ............ verified-fields-only call/account brief
- dedupe_prospects ............. normalized identity dedupe (first wins)
- crm_overlay_proposal ......... proposal-only CRM overlay (never mutates)
- classify_sales_reply ......... sales-pipeline reply states for the P4 lane
                                (READY_TO_BUY/ASKS_FOR_SAMPLE/ASKS_FOR_DEMO/
                                PRICE_OBJECTION/TIMING_OBJECTION/NEEDS_INFO/
                                NOT_INTERESTED/WRONG_PERSON/INTERESTED/UNKNOWN)

There is deliberately NO send function. Outreach execution lives behind
ProductionGate HUMAN_APPROVED + credentials, outside this module.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

ResponseLabel = Literal[
    "INTERESTED",
    "QUESTION",
    "OBJECTION",
    "NOT_NOW",
    "NOT_A_FIT",
    "UNSUBSCRIBE",
    "UNKNOWN",
]

# Order matters: UNSUBSCRIBE first (safety), explicit disinterest before
# interest ("not interested" contains "interested"), positives before
# questions ("what's the price? we're interested" is still engaged, but a
# bare question routes to QUESTION for a human/templated answer).
_UNSUBSCRIBE = re.compile(r"unsub|stop\b|remove me|do not (contact|email|call|write)|opt.?out", re.I)
_NOT_A_FIT = re.compile(r"not (a good )?fit|not interested|no thanks|\bpass\b|already (have|use)|no budget|too expensive|wrong person", re.I)
_INTERESTED = re.compile(r"\binterested\b|let'?s talk|\bbook\b.{0,20}\b(call|demo|meeting)|\bsend\b.{0,20}\b(proposal|info|deck|pricing)|\bcall me\b|\byes\b.{0,20}\b(demo|call)", re.I)
_QUESTION = re.compile(r"\?", re.I)
_OBJECTION = re.compile(r"how much|price|cost|concern|risk|what about|what if|\bbut\b|contract|guarantee|reference", re.I)
_NOT_NOW = re.compile(r"not now|later|next quarter|busy|follow up|revisit|timing", re.I)


def response_classifier(text: Any) -> dict[str, Any]:
    """Classify one inbound message. Non-string input is UNKNOWN (fail-closed)."""
    if not isinstance(text, str) or not text.strip():
        return {"label": "UNKNOWN", "reasons": ["empty_or_non_string_input"]}
    lowered = text.strip()
    if _UNSUBSCRIBE.search(lowered):
        return {"label": "UNSUBSCRIBE", "reasons": ["opt_out_language"],
                "required_action": "suppress_immediately"}
    if _NOT_A_FIT.search(lowered):
        return {"label": "NOT_A_FIT", "reasons": ["explicit_disinterest_or_mismatch"]}
    if _INTERESTED.search(lowered) and not _QUESTION.search(lowered):
        return {"label": "INTERESTED", "reasons": ["explicit_positive_intent"],
                "required_action": "route_to_sales"}
    if _QUESTION.search(lowered):
        return {"label": "QUESTION", "reasons": ["question_asked"],
                "required_action": "answer_from_evidence_only"}
    if _OBJECTION.search(lowered):
        return {"label": "OBJECTION", "reasons": ["objection_keyword"],
                "required_action": "handle_with_verified_proof_only"}
    if _NOT_NOW.search(lowered):
        return {"label": "NOT_NOW", "reasons": ["timing_deferral"],
                "required_action": "nurture_no_send_without_approval"}
    if _INTERESTED.search(lowered):
        return {"label": "INTERESTED", "reasons": ["explicit_positive_intent"],
                "required_action": "route_to_sales"}
    return {"label": "UNKNOWN", "reasons": ["no_signal_matched"],
            "required_action": "human_review"}


# --- account scoring (transparent, explained) ---------------------------------

@dataclass(slots=True)
class AccountScore:
    score: float
    tier: Literal["QUALIFIED", "NEEDS_REVIEW", "DISQUALIFIED"]
    factors: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_SCORE_WEIGHTS = {
    "icp_fit": 0.30,
    "problem_signal": 0.25,
    "evidence_quality": 0.20,
    "contactability": 0.15,
    "timing_signal": 0.10,
}


def _clamp01(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def score_account(signals: dict[str, Any]) -> AccountScore:
    """Transparent weighted score from explicit 0..1 factor inputs.

    Missing factors score 0 (never assumed). ≥0.70 QUALIFIED,
    0.40–0.70 NEEDS_REVIEW, <0.40 DISQUALIFIED. Deterministic.
    """
    if not isinstance(signals, dict):
        return AccountScore(score=0.0, tier="DISQUALIFIED",
                            reasons=["malformed_signals_not_a_dict"])
    factors = {name: _clamp01(signals.get(name, 0.0)) for name in _SCORE_WEIGHTS}
    total = round(sum(factors[name] * weight for name, weight in _SCORE_WEIGHTS.items()), 4)
    reasons = [f"{name}_weak" for name, value in factors.items() if value < 0.4]
    tier = "QUALIFIED" if total >= 0.70 else ("NEEDS_REVIEW" if total >= 0.40 else "DISQUALIFIED")
    return AccountScore(score=total, tier=tier, factors=factors, reasons=sorted(reasons))


# --- outreach drafting (evidence-only, fail-closed claims) --------------------

# Any of these in the FINAL draft (including caller-supplied fields) rejects it.
_BANNED_CLAIMS = [
    r"\broi\b", r"return on investment", r"\bguarantee", r"risk.?free",
    r"\btestimonial", r"\breview\b.{0,10}[★5]", r"5.?star", r"#1\b",
    r"\bbest\b.{0,15}\b(agency|tool|platform|service)\b",
    r"save \d+\s?%", r"\d+\s?x\b.{0,10}\b(return|revenue|results)\b",
    r"\$[\d,]+.{0,20}\b(revenue|profit|results)\b",
]


def _banned_hits(text: str) -> list[str]:
    lowered = text.lower()
    return [pat for pat in _BANNED_CLAIMS if re.search(pat, lowered)]


@dataclass(slots=True)
class OutreachDraft:
    subject: str
    body: str
    claims_used: list[str] = field(default_factory=list)
    evidence_ids: list[str] = field(default_factory=list)
    status: Literal["draft_pending_review"] = "draft_pending_review"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def draft_outreach(*, prospect: dict[str, Any], problem: str,
                   proof: str, evidence_ids: list[str]) -> OutreachDraft:
    """Build a draft from verified fields only. Banned claims raise ValueError.

    No sending happens here or anywhere in this module.
    """
    if not isinstance(prospect, dict) or not prospect.get("company"):
        raise ValueError("draft_outreach: prospect.company is required")
    if not problem or not problem.strip():
        raise ValueError("draft_outreach: problem is required")
    if not proof or not proof.strip():
        raise ValueError("draft_outreach: proof is required")
    if not evidence_ids:
        raise ValueError("draft_outreach: evidence_ids are required")
    name = str(prospect.get("contact_name") or "there").strip()
    company = str(prospect["company"]).strip()
    subject = f"Idea for {company}: {problem.strip()[:60]}"
    body = (
        f"Hi {name},\n\n"
        f"Noticed {company} may be dealing with {problem.strip()}.\n\n"
        f"Relevant proof: {proof.strip()}\n\n"
        f"Open to a 10-minute look next week?\n\n"
        f"-- {prospect.get('sender_name', 'MBM')}"
    )
    hits = _banned_hits(subject + "\n" + body)
    if hits:
        raise ValueError(f"draft_outreach: banned claim patterns rejected: {hits}")
    return OutreachDraft(subject=subject, body=body,
                         claims_used=[problem.strip(), proof.strip()],
                         evidence_ids=list(evidence_ids))


# --- sales brief (verified fields only) ---------------------------------------

@dataclass(slots=True)
class SalesBrief:
    account: str
    pain: str
    evidence: list[str] = field(default_factory=list)
    discovery_questions: list[str] = field(default_factory=list)
    objection_notes: list[str] = field(default_factory=list)
    next_action: str = "human_review_before_outreach"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_sales_brief(*, company: str, pain: str,
                      evidence_ids: list[str]) -> SalesBrief:
    if not company or not company.strip():
        raise ValueError("build_sales_brief: company is required")
    if not pain or not pain.strip():
        raise ValueError("build_sales_brief: pain is required")
    if not evidence_ids:
        raise ValueError("build_sales_brief: evidence_ids are required")
    return SalesBrief(
        account=company.strip(),
        pain=pain.strip(),
        evidence=list(evidence_ids),
        discovery_questions=[
            "How is this handled today?",
            "What breaks when volume doubles?",
            "Who owns this outcome?",
        ],
        objection_notes=["answer only from attached evidence; say 'I don't know' otherwise"],
    )


# --- dedupe + CRM proposal -----------------------------------------------------

def _norm(value: Any) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").lower())


def dedupe_prospects(prospects: list[dict[str, Any]]) -> dict[str, Any]:
    """Dedupe by normalized (domain or company + contact). First wins.

    Returns {kept, duplicates} with duplicate_of pointers. Fail-closed on shape.
    """
    if not isinstance(prospects, list):
        raise ValueError("dedupe_prospects: prospects must be a list")
    seen: dict[str, int] = {}
    kept: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    for index, item in enumerate(prospects):
        if not isinstance(item, dict):
            raise ValueError(f"dedupe_prospects: row {index} is not a dict")
        domain = _norm(item.get("domain"))
        company = _norm(item.get("company"))
        contact = _norm(item.get("contact_name") or item.get("email"))
        key = domain or f"{company}|{contact}"
        if not key.strip("|"):
            raise ValueError(f"dedupe_prospects: row {index} has no identity")
        if key in seen:
            duplicates.append({"index": index, "duplicate_of_index": seen[key]})
        else:
            seen[key] = index
            kept.append(item)
    return {"kept": kept, "duplicates": duplicates,
            "kept_count": len(kept), "duplicate_count": len(duplicates)}


def crm_overlay_proposal(*, entity_id: str, stage: str,
                         evidence_ids: list[str],
                         activity: str) -> dict[str, Any]:
    """Proposal-only CRM overlay. Never writes to any CRM.

    Execution requires CONTROLLED_WRITE approval downstream; this function
    only shapes the proposal so the approval gate has something to review.
    """
    if not entity_id or not str(entity_id).strip():
        raise ValueError("crm_overlay_proposal: entity_id is required")
    if not evidence_ids:
        raise ValueError("crm_overlay_proposal: evidence_ids are required")
    return {
        "object_type": "CRM_OVERLAY_PROPOSAL",
        "entity_id": str(entity_id).strip(),
        "proposed_stage": stage,
        "activity": activity,
        "evidence_ids": list(evidence_ids),
        "executed": False,
        "execution": "requires_controlled_write_approval",
    }


# --- sales reply handling (P4 lane states) --------------------------------------

SalesReplyLabel = Literal[
    "READY_TO_BUY",
    "ASKS_FOR_SAMPLE",
    "ASKS_FOR_DEMO",
    "PRICE_OBJECTION",
    "TIMING_OBJECTION",
    "NEEDS_INFO",
    "NOT_INTERESTED",
    "WRONG_PERSON",
    "INTERESTED",
    "UNKNOWN",
]

# Order: buying intent first, then specific asks, then objections, then
# disinterest, then info needs; UNKNOWN is the fail-closed fallback.
_SALES_READY = re.compile(
    r"ready to (buy|start|move forward)|let'?s do it|send (me )?(the )?(invoice|payment link|contract)|where do I (pay|sign)", re.I)
_SALES_SAMPLE = re.compile(r"sample|trial|test (it|run)|free sample|\bpilot\b", re.I)
_SALES_DEMO = re.compile(r"\bdemo\b|demonstration|show me|walk ?through|can I see", re.I)
_SALES_PRICE = re.compile(r"price|cost|how much|expensive|cheaper|discount|budget", re.I)
_SALES_TIMING = re.compile(r"not now|\blater\b|timing|next quarter|\bbusy\b|follow up|revisit", re.I)
_SALES_WRONG = re.compile(r"wrong person|not (me|mine|my department)|forward to|right person|no longer (here|with)", re.I)
_SALES_NO = re.compile(r"not interested|no thanks|\bpass\b|remove me|\bstop\b|unsub|no need|not a (good )?fit", re.I)
_SALES_INFO = re.compile(r"\?|more (info|detail)|how does|what (do|does|is)|explain|tell me more", re.I)
_SALES_YES = re.compile(r"\binterested\b|let'?s talk|\bbook\b|call me|send (more|info|details)", re.I)

_SALES_NEXT_ACTION = {
    "READY_TO_BUY": "open_customer_job_immediately",
    "ASKS_FOR_SAMPLE": "offer_free_sample_run_then_paid_pilot",
    "ASKS_FOR_DEMO": "send_demo_run_summary_then_book_call",
    "PRICE_OBJECTION": "restate_499_scope_no_discount_without_approval",
    "TIMING_OBJECTION": "nurture_with_permission_only",
    "NEEDS_INFO": "answer_from_offer_doc_only",
    "NOT_INTERESTED": "suppress_immediately_no_further_contact",
    "WRONG_PERSON": "ask_for_referral_once_then_suppress_if_refused",
    "INTERESTED": "route_to_sales_for_discovery_call",
    "UNKNOWN": "human_review",
}


def classify_sales_reply(text: Any) -> dict[str, Any]:
    """Classify one sales reply into P4 pipeline states. No sending."""
    if not isinstance(text, str) or not text.strip():
        return {"label": "UNKNOWN", "reasons": ["empty_or_non_string_input"],
                "required_action": _SALES_NEXT_ACTION["UNKNOWN"]}
    lowered = text.strip()
    if _SALES_READY.search(lowered):
        label = "READY_TO_BUY"
    elif _SALES_SAMPLE.search(lowered):
        label = "ASKS_FOR_SAMPLE"
    elif _SALES_DEMO.search(lowered):
        label = "ASKS_FOR_DEMO"
    elif _SALES_NO.search(lowered):
        label = "NOT_INTERESTED"
    elif _SALES_WRONG.search(lowered):
        label = "WRONG_PERSON"
    elif _SALES_PRICE.search(lowered):
        label = "PRICE_OBJECTION"
    elif _SALES_TIMING.search(lowered):
        label = "TIMING_OBJECTION"
    elif _SALES_INFO.search(lowered):
        label = "NEEDS_INFO"
    elif _SALES_YES.search(lowered):
        label = "INTERESTED"
    else:
        label = "UNKNOWN"
    reasons = ["matched_" + label.lower()] if label != "UNKNOWN" else ["no_signal_matched"]
    if label == "NOT_INTERESTED" and _UNSUBSCRIBE.search(lowered):
        reasons.append("opt_out_language_present")
    return {"label": label, "reasons": reasons,
            "required_action": _SALES_NEXT_ACTION[label]}
