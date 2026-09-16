"""Creator Acquisition Gate (#65).

Deterministic evidence gate for creator acquisition.

Contract:
- Enforce >= 20,000 evidenced audience.
- Require: platform, profile, audience_type, audience_count,
  evidence_url/source, timestamp.
- Reject missing, malformed, future, or stale evidence.
- Deterministic reason codes (stable strings, no LLM).
- Audience evidence is explicitly ISOLATED from buyer intent,
  conversion, revenue, or product-market fit claims.

Integration:
- Used only where the existing acquisition/revenue architecture
  requires it (DemandFactory creator_loop qualification path).
- Does NOT mutate external systems. Proposal/validation only.
- Unknown / ambiguous input = FAIL CLOSED (rejected).

Stale threshold: evidence older than 90 days is STALE.
Documented here and enforced deterministically.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal
from urllib.parse import urlparse

CREATOR_MIN_AUDIENCE = 20000
EVIDENCE_MAX_AGE_DAYS = 90

GateStatus = Literal["qualified", "rejected"]


# Deterministic reason codes (stable contract).
REASONS = {
    "MISSING_PLATFORM": "MISSING_PLATFORM",
    "MISSING_PROFILE": "MISSING_PROFILE",
    "MISSING_AUDIENCE_TYPE": "MISSING_AUDIENCE_TYPE",
    "MISSING_AUDIENCE_COUNT": "MISSING_AUDIENCE_COUNT",
    "MISSING_EVIDENCE_URL": "MISSING_EVIDENCE_URL",
    "MISSING_EVIDENCE_SOURCE": "MISSING_EVIDENCE_SOURCE",
    "MISSING_TIMESTAMP": "MISSING_TIMESTAMP",
    "MALFORMED_AUDIENCE_COUNT": "MALFORMED_AUDIENCE_COUNT",
    "MALFORMED_EVIDENCE_URL": "MALFORMED_EVIDENCE_URL",
    "MALFORMED_TIMESTAMP": "MALFORMED_TIMESTAMP",
    "MALFORMED_PLATFORM": "MALFORMED_PLATFORM",
    "MALFORMED_PROFILE": "MALFORMED_PROFILE",
    "MALFORMED_AUDIENCE_TYPE": "MALFORMED_AUDIENCE_TYPE",
    "FUTURE_EVIDENCE": "FUTURE_EVIDENCE",
    "STALE_EVIDENCE": "STALE_EVIDENCE",
    "BELOW_THRESHOLD": "BELOW_THRESHOLD",
}


@dataclass(slots=True)
class CreatorEvidence:
    """Raw evidence submitted for one creator."""

    platform: str = ""
    profile: str = ""
    audience_type: str = ""
    audience_count: Any = None
    evidence_url: str = ""
    evidence_source: str = ""
    timestamp: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class CreatorGateResult:
    status: GateStatus
    audience_count: int = 0
    reasons: list[str] = field(default_factory=list)
    # Explicit isolation disclaimer: audience size is NOT intent/conversion/revenue/PMF.
    isolation_note: str = (
        "audience_evidence_is_not_intent: audience size MUST NOT be interpreted "
        "as buyer intent, conversion, revenue, or product-market fit."
    )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        return d

    @property
    def qualified(self) -> bool:
        return self.status == "qualified"


def _parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    # Accept ISO8601 with Z suffix.
    try:
        normalized = text.replace("Z", "+00:00") if text.endswith("Z") else text
        parsed = datetime.fromisoformat(normalized)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except Exception:
        return None


def _valid_url(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip():
        return False
    try:
        parsed = urlparse(value.strip())
        return parsed.scheme.lower() in ("http", "https") and bool(parsed.hostname)
    except Exception:
        return False


def _parse_audience_count(value: Any) -> int | None:
    # Strict: int or digit-only string. Reject floats, None, objects.
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        text = value.strip().replace(",", "").replace("_", "")
        if not text:
            return None
        # Reject floats / decimals explicitly.
        if "." in text or "e" in text.lower():
            return None
        if text.startswith("+"):
            text = text[1:]
        if text.startswith("-"):
            # Negative is well-formed int but will fail threshold below;
            # still parse it so the failure is BELOW_THRESHOLD, not malformed?
            # Deterministic choice: negative counts are MALFORMED (nonsense input).
            return None
        if not text.isdigit():
            return None
        try:
            return int(text)
        except Exception:
            return None
    return None


def evaluate_creator_evidence(
    evidence: CreatorEvidence | dict[str, Any],
    *,
    now: datetime | None = None,
) -> CreatorGateResult:
    """Deterministically evaluate creator evidence. Fail-closed.

    `now` is injectable for deterministic tests; defaults to UTC now.
    """
    if isinstance(evidence, dict):
        evidence = CreatorEvidence(
            platform=evidence.get("platform", ""),
            profile=evidence.get("profile", ""),
            audience_type=evidence.get("audience_type", ""),
            audience_count=evidence.get("audience_count"),
            evidence_url=evidence.get("evidence_url", ""),
            evidence_source=evidence.get("evidence_source", ""),
            timestamp=evidence.get("timestamp", ""),
        )

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)

    reasons: list[str] = []

    # --- required-field presence ---
    if not isinstance(evidence.platform, str) or not evidence.platform.strip():
        reasons.append(REASONS["MISSING_PLATFORM"])
    if not isinstance(evidence.profile, str) or not evidence.profile.strip():
        reasons.append(REASONS["MISSING_PROFILE"])
    if not isinstance(evidence.audience_type, str) or not evidence.audience_type.strip():
        reasons.append(REASONS["MISSING_AUDIENCE_TYPE"])
    if evidence.audience_count is None or (isinstance(evidence.audience_count, str) and not evidence.audience_count.strip()):
        reasons.append(REASONS["MISSING_AUDIENCE_COUNT"])
    if not isinstance(evidence.evidence_url, str) or not evidence.evidence_url.strip():
        reasons.append(REASONS["MISSING_EVIDENCE_URL"])
    if not isinstance(evidence.evidence_source, str) or not evidence.evidence_source.strip():
        reasons.append(REASONS["MISSING_EVIDENCE_SOURCE"])
    if not isinstance(evidence.timestamp, str) or not evidence.timestamp.strip():
        reasons.append(REASONS["MISSING_TIMESTAMP"])

    # --- malformed checks (only where field present) ---
    count: int | None = None
    if REASONS["MISSING_AUDIENCE_COUNT"] not in reasons:
        count = _parse_audience_count(evidence.audience_count)
        if count is None:
            reasons.append(REASONS["MALFORMED_AUDIENCE_COUNT"])

    if REASONS["MISSING_EVIDENCE_URL"] not in reasons:
        if not _valid_url(evidence.evidence_url):
            reasons.append(REASONS["MALFORMED_EVIDENCE_URL"])

    parsed_ts: datetime | None = None
    if REASONS["MISSING_TIMESTAMP"] not in reasons:
        parsed_ts = _parse_timestamp(evidence.timestamp)
        if parsed_ts is None:
            reasons.append(REASONS["MALFORMED_TIMESTAMP"])

    # Malformed string-type fields: non-string types are malformed, not missing.
    # (Missing already covers empty strings above.)
    for attr, code in (
        ("platform", REASONS["MALFORMED_PLATFORM"]),
        ("profile", REASONS["MALFORMED_PROFILE"]),
        ("audience_type", REASONS["MALFORMED_AUDIENCE_TYPE"]),
    ):
        value = getattr(evidence, attr)
        if value is not None and not isinstance(value, str):
            if f"MISSING_{attr.upper()}" not in reasons:
                reasons.append(code)

    # --- temporal checks ---
    if parsed_ts is not None:
        if parsed_ts > current:
            reasons.append(REASONS["FUTURE_EVIDENCE"])
        else:
            age_days = (current - parsed_ts).total_seconds() / 86400.0
            if age_days > EVIDENCE_MAX_AGE_DAYS:
                reasons.append(REASONS["STALE_EVIDENCE"])

    # --- threshold ---
    if count is not None and REASONS["MALFORMED_AUDIENCE_COUNT"] not in reasons:
        if count < CREATOR_MIN_AUDIENCE:
            reasons.append(REASONS["BELOW_THRESHOLD"])

    if reasons:
        # Deterministic ordering for stable evidence.
        ordered = sorted(set(reasons))
        return CreatorGateResult(status="rejected", audience_count=count or 0, reasons=ordered)

    return CreatorGateResult(status="qualified", audience_count=count or 0, reasons=[])


def qualify_creator_with_evidence(
    creator_score: float,
    evidence: CreatorEvidence | dict[str, Any],
    *,
    minimum_score: float = 0.62,
    now: datetime | None = None,
) -> CreatorGateResult:
    """Gate + score integration point.

    Evidence gate runs FIRST (fail-closed). Score threshold runs second.
    Audience count is never mapped to intent/conversion/revenue.
    """
    gate = evaluate_creator_evidence(evidence, now=now)
    if gate.status != "qualified":
        return gate
    if not isinstance(creator_score, (int, float)) or creator_score < minimum_score:
        return CreatorGateResult(
            status="rejected",
            audience_count=gate.audience_count,
            reasons=["BELOW_THRESHOLD"],
        )
    return gate


def assert_audience_isolation(result_dict: dict[str, Any]) -> None:
    """Guard: audience evidence must never masquerade as commercial proof.

    Raises ValueError if forbidden intent/revenue keys are present.
    """
    forbidden = {
        "buyer_intent",
        "conversion",
        "conversion_rate",
        "revenue",
        "gross_revenue",
        "net_revenue",
        "pmf",
        "product_market_fit",
    }
    present = forbidden.intersection(set(result_dict.keys()))
    if present:
        raise ValueError(
            f"audience evidence MUST NOT be interpreted as commercial proof: {sorted(present)}"
        )
