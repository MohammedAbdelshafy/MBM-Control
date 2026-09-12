"""Central policy / plugin layer (P0.4).

Single home for authorization, approval/HITL, audit, correlation IDs, secret
redaction, cost/budget hooks, retry/timeout policy, and side-effect
classification. Agents MUST NOT duplicate these rules locally — they call
:func:`evaluate` and enforce the returned decision.

Side-effect taxonomy (deterministic, mechanical — no LLM involved):

    READ                  -> automatic (repo reads, lead-data reads, drafts)
    SAFE_WRITE            -> automatic within declared write_scope (drafts, working state)
    GATED_WRITE           -> policy check (canonical lead state via single-writer)
    EXTERNAL_SIDE_EFFECT  -> approval + domain gate (email/SMS/call/suppression-checked)
    HIGH_IMPACT           -> hard approval gate, human owner (deploy prod, delete infra)

Security invariants: secrets are never recorded (see :func:`redact`), never
logged in full, and never leave the server boundary.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ActionClass(str, Enum):
    READ = "READ"
    SAFE_WRITE = "SAFE_WRITE"
    GATED_WRITE = "GATED_WRITE"
    EXTERNAL_SIDE_EFFECT = "EXTERNAL_SIDE_EFFECT"
    HIGH_IMPACT = "HIGH_IMPACT"


class PolicyVerdict(str, Enum):
    ALLOW = "ALLOW"  # automatic
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"  # human or delegated approver must sign
    DENY = "DENY"  # hard gate, never auto-overridable


@dataclass(frozen=True)
class PolicyDecision:
    action: str
    action_class: ActionClass
    verdict: PolicyVerdict
    gates: List[str]  # domain gates that must additionally pass (advisory names)
    reason: str
    correlation_id: str
    approval: Optional[Dict[str, Any]] = None


# -- deterministic classification table ---------------------------------------
# Ordered rules: first match wins. Keep mechanical; reasoning lives in agents.
_CLASSIFICATION_RULES: List[tuple] = [
    # HIGH_IMPACT / irreversible
    (re.compile(r"\b(delete|destroy|drop|terminate)\b.*\b(infra|database|table|bucket|project)\b", re.I), ActionClass.HIGH_IMPACT, "destructive infrastructure operation"),
    (re.compile(r"\bdeploy\b.*\bprod", re.I), ActionClass.HIGH_IMPACT, "production deployment"),
    # EXTERNAL side effects (real-world, money, or compliance surface)
    (re.compile(r"\b(place|make).{0,20}\bcall\b|\bauto.?dial\b|\bbridge\b.*\bcall\b", re.I), ActionClass.EXTERNAL_SIDE_EFFECT, "real outbound call"),
    (re.compile(r"\bsend\b.*\b(sms|whatsapp|message)\b|\bsms\b.*\b(blast|send|campaign)\b", re.I), ActionClass.EXTERNAL_SIDE_EFFECT, "real outbound SMS/message"),
    (re.compile(r"\bsend\b.*\bemail\b|\bemail\b.*\b(dispatch|blast|send)\b", re.I), ActionClass.EXTERNAL_SIDE_EFFECT, "real outbound email"),
    (re.compile(r"\b(spend|charge|purchase|payout|withdraw)\b", re.I), ActionClass.EXTERNAL_SIDE_EFFECT, "money movement"),
    # GATED writes (canonical business state)
    (re.compile(r"\b(canonical|leads_database|lead state|dialer state|suppression list)\b.*\b(writ|updat|modif|purge|delet|ingest)\b", re.I), ActionClass.GATED_WRITE, "canonical business state mutation"),
    (re.compile(r"\b(record|persist).{0,20}\bafter.?call\b|\bdisposition\b.*\b(writ|save|persist)\b", re.I), ActionClass.GATED_WRITE, "after-call persistence"),
    # SAFE writes (reversible, scoped)
    (re.compile(r"\b(draft|working state|session state|artifact|report|cache)\b.*\b(writ|save|updat|generat)\b", re.I), ActionClass.SAFE_WRITE, "scoped reversible write"),
    (re.compile(r"\bgenerat.{0,10}\bdraft\b", re.I), ActionClass.SAFE_WRITE, "draft generation"),
]


def classify(action: str) -> tuple:
    """Return (ActionClass, matched_reason). Defaults to READ for pure reads,
    GATED_WRITE for anything unrecognized that mutates (fail-closed)."""
    for pattern, cls, reason in _CLASSIFICATION_RULES:
        if pattern.search(action):
            return cls, reason
    if re.search(r"\b(read|get|list|fetch|inspect|audit|query|draft|plan|review|check|status|monitor)\b", action, re.I):
        return ActionClass.READ, "read-only operation"
    if re.search(r"\b(writ|updat|modif|delet|creat|push|commit|send|call|publish|deploy)\b", action, re.I):
        return ActionClass.GATED_WRITE, "unrecognized mutation fails closed to gated write"
    return ActionClass.GATED_WRITE, "unrecognized action fails closed to gated write"


# Domain gates that must additionally pass per action class / reason.
_GATE_MAP: Dict[str, List[str]] = {
    "real outbound call": ["dialer_verification_gate", "provider_abstraction", "cooldown_dnc_suppression", "idempotency"],
    "real outbound SMS/message": ["opt_out_suppression", "provider_abstraction", "dry_run_default"],
    "real outbound email": ["email_suppression", "sender_verification", "sequencing", "approval"],
    "money movement": ["budget_limit", "approval"],
    "canonical business state mutation": ["single_writer_lock", "verification_gate", "provenance"],
    "after-call persistence": ["single_writer_lock", "idempotency"],
    "production deployment": ["approval", "health_checks", "rollback_plan"],
    "destructive infrastructure operation": ["hard_gate_human_approval"],
}


def new_correlation_id() -> str:
    return f"cp-{uuid.uuid4().hex[:12]}"


# Severity order for escalation (higher index = more dangerous).
_SEVERITY = {
    ActionClass.READ: 0,
    ActionClass.SAFE_WRITE: 1,
    ActionClass.GATED_WRITE: 2,
    ActionClass.EXTERNAL_SIDE_EFFECT: 3,
    ActionClass.HIGH_IMPACT: 4,
}


# Gates for explicitly declared tool permissions (used when evaluate() is
# given action_class; the free-text _GATE_MAP stays authoritative otherwise).
_DECLARED_GATES: Dict[ActionClass, List[str]] = {
    ActionClass.READ: [],
    ActionClass.SAFE_WRITE: [],
    ActionClass.GATED_WRITE: ["approval"],
    ActionClass.EXTERNAL_SIDE_EFFECT: ["approval", "domain_gate"],
    ActionClass.HIGH_IMPACT: ["hard_gate_human_approval"],
}


def resolve_class(
    action: str, declared: Optional[ActionClass] = None
) -> tuple:
    """Single home for class resolution. Returns (ActionClass, reason, gates).

    declared=None -> fail-closed text classification. Declared wins, except
    text proving EXTERNAL/HIGH_IMPACT escalates over a weaker declaration.
    """
    if declared is None:
        cls, reason = classify(action)
        return cls, reason, list(_GATE_MAP.get(reason, []))
    derived, text_reason = classify(action)
    if (derived in (ActionClass.EXTERNAL_SIDE_EFFECT, ActionClass.HIGH_IMPACT)
            and _SEVERITY[derived] > _SEVERITY[declared]):
        return (
            derived,
            (f"escalated to {derived.value} from action text "
             f"({text_reason}); declaration was weaker"),
            list(_GATE_MAP.get(text_reason, _DECLARED_GATES[derived])),
        )
    return declared, f"declared tool permission: {declared.value}", list(_DECLARED_GATES[declared])


def evaluate(
    action: str,
    context: Optional[Dict[str, Any]] = None,
    approval: Optional[Dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
    action_class: Optional[ActionClass] = None,
) -> PolicyDecision:
    """Deterministic policy gate. Pure function of (action, approval).

    Class resolution lives in resolve_class (single home); this function owns
    the verdict. Tool registration is a deploy-time trust boundary; escalation
    is the backstop, code review of registrations is the front line.
    """
    context = context or {}
    action_class, reason, gates = resolve_class(action, action_class)
    cid = correlation_id or new_correlation_id()

    if action_class is ActionClass.READ:
        return PolicyDecision(action, action_class, PolicyVerdict.ALLOW, gates, f"automatic: {reason}", cid)
    if action_class is ActionClass.SAFE_WRITE:
        return PolicyDecision(action, action_class, PolicyVerdict.ALLOW, gates, f"automatic in scope: {reason}", cid)
    if action_class is ActionClass.GATED_WRITE:
        return PolicyDecision(
            action, action_class, PolicyVerdict.REQUIRE_APPROVAL, gates,
            f"policy check required: {reason}", cid, approval,
        )
    # EXTERNAL_SIDE_EFFECT and HIGH_IMPACT
    if approval and approval.get("approved") is True:
        return PolicyDecision(
            action, action_class, PolicyVerdict.ALLOW, gates,
            f"approved by {approval.get('approver', 'unknown')}: {reason}", cid, approval,
        )
    return PolicyDecision(
        action, action_class,
        PolicyVerdict.DENY if action_class is ActionClass.HIGH_IMPACT and _is_hard(action) else PolicyVerdict.REQUIRE_APPROVAL,
        gates, f"approval gate: {reason}", cid, approval,
    )


def _is_hard(action: str) -> bool:
    # Destructive infra without approval is DENY (not merely "needs approval"),
    # so callers cannot treat silence as consent.
    return bool(re.search(r"\b(delete|destroy|drop|terminate)\b", action, re.I))


# -- secret redaction -----------------------------------------------------------
# Never record secrets in runs, logs, lead JSON, or reports.
_SECRET_PATTERNS: List[re.Pattern] = [
    re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd|pwd|bearer|session[_-]?key)\s*[:=]\s*['\"]?([^\s'\",}]+)['\"]?"),
    re.compile(r"\b(sk-[A-Za-z0-9_-]{8,})"),
    re.compile(r"\b(xox[bap]-[A-Za-z0-9-]+)"),
    re.compile(r"\b(ghp_[A-Za-z0-9]{8,})"),
    re.compile(r"\b(AKIA[0-9A-Z]{16})"),
    re.compile(r"\b(\+?\d[\d\s\-().]{7,}\d)"),  # phone numbers in tool args/logs
]

REDACTED = "[REDACTED]"


def redact(value: Any) -> Any:
    """Recursively redact secret-looking values. Safe for tool args, outputs, errors."""
    if isinstance(value, str):
        out = value
        out = _SECRET_PATTERNS[0].sub(lambda m: m.group(0).split(m.group(2))[0] + REDACTED, out)
        for pat in _SECRET_PATTERNS[1:]:
            out = pat.sub(REDACTED, out)
        return out
    if isinstance(value, dict):
        return {
            k: (REDACTED if re.search(r"(?i)(token|secret|password|api[_-]?key|auth|credential|phone)", str(k)) else redact(v))
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


# -- retry / timeout policy (safe defaults) --------------------------------------
# Retry ONLY safe/transient failures where the caller proves no side effect
# occurred (mirrors phound_provider.TRANSIENT_ERRORS semantics).
TRANSIENT_ERRORS = frozenset({"timeout", "connection_error", "provider_unavailable", "rate_limited"})

DEFAULT_TIMEOUTS = {
    "tool_call_sec": 30,
    "provider_call_sec": 60,
    "workflow_run_sec": 3600,
}

DEFAULT_RETRY = {
    "max_attempts": 3,
    "backoff_sec": 2.0,
    "retryable_errors": sorted(TRANSIENT_ERRORS),
}


def retry_allowed(error_kind: str, side_effect_proven_absent: bool) -> bool:
    return error_kind in TRANSIENT_ERRORS and side_effect_proven_absent
