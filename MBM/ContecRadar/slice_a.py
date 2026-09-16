"""Commercial Radar Slice A (#62) — approved deterministic offline scope.

Slice A is OFFLINE ONLY:
- ingest in-memory signal dicts
- cluster -> score -> decide (reuses ContecRadar deterministic engines)
- return ranked opportunities + evidence trace

Explicit exclusions (enforced by fail-closed guards):
- no outbound sending
- no campaign execution
- no external DB/runtime mutation
- no autonomous approval queue
- no demo-generation scope creep

Any attempt to invoke an excluded operation raises ExcludedOperationError.
No network, no filesystem writes, no external side effects.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


class ExcludedOperationError(RuntimeError):
    """Raised when Slice A is asked to perform an excluded operation."""


SLICE_A_SCOPE = "offline_signal_to_ranked_opportunity"
SLICE_A_EXCLUSIONS = [
    "no_outbound_sending",
    "no_campaign_execution",
    "no_external_db_runtime_mutation",
    "no_autonomous_approval_queue",
    "no_demo_generation",
]


@dataclass(slots=True)
class SliceASignal:
    signal_id: str
    title: str = ""
    body: str = ""
    source: str = "offline_fixture"
    url: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class SliceAResult:
    scope: str = SLICE_A_SCOPE
    opportunities: list[dict[str, Any]] = field(default_factory=list)
    exclusions_preserved: list[str] = field(default_factory=list)
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _require_signal_shape(item: dict[str, Any]) -> SliceASignal:
    if not isinstance(item, dict):
        raise ValueError("slice_a signal must be a dict")
    signal_id = item.get("signal_id", "")
    if not isinstance(signal_id, str) or not signal_id.strip():
        raise ValueError("slice_a signal missing signal_id")
    return SliceASignal(
        signal_id=signal_id.strip(),
        title=str(item.get("title", "")),
        body=str(item.get("body", "")),
        source=str(item.get("source", "offline_fixture")),
        url=str(item.get("url", "")),
    )


def run_slice_a(signals: list[dict[str, Any]]) -> SliceAResult:
    """Deterministic offline run: signals -> ranked opportunities.

    Reuses MBM.ContecRadar analyzer/clustering/decision in-memory.
    Never touches network, filesystem, or external runtimes.
    """
    from MBM.ContecRadar.analyzer import signals_to_cards
    from MBM.ContecRadar.clustering import cluster_card
    from MBM.ContecRadar.decision import enrich_and_decide
    from MBM.ContecRadar.models import Opportunity, Signal

    parsed = [_require_signal_shape(s) for s in signals]
    lib_signals = [
        Signal(signal_id=p.signal_id, source=p.source, url=p.url, title=p.title, body=p.body)
        for p in parsed
    ]
    cards = signals_to_cards(lib_signals)
    opportunities: list[Opportunity] = []
    for card in cards:
        opp = cluster_card(card, opportunities)
        enrich_and_decide(opp)
        # Ensure in-memory list tracks the touched opportunity.
        if opp not in opportunities:
            opportunities.append(opp)
    ranked = sorted(opportunities, key=lambda o: o.score, reverse=True)
    return SliceAResult(
        opportunities=[o.to_dict() for o in ranked],
        exclusions_preserved=list(SLICE_A_EXCLUSIONS),
        diagnostics={
            "signal_count": len(parsed),
            "opportunity_count": len(ranked),
            "side_effects": "none",
            "writes": "none",
        },
    )


# --- exclusion guards (fail-closed) ---

def send_outreach(*args: Any, **kwargs: Any) -> Any:
    raise ExcludedOperationError("Slice A exclusion: no_outbound_sending")


def execute_campaign(*args: Any, **kwargs: Any) -> Any:
    raise ExcludedOperationError("Slice A exclusion: no_campaign_execution")


def mutate_external_db(*args: Any, **kwargs: Any) -> Any:
    raise ExcludedOperationError("Slice A exclusion: no_external_db_runtime_mutation")


def autonomous_approve(*args: Any, **kwargs: Any) -> Any:
    raise ExcludedOperationError("Slice A exclusion: no_autonomous_approval_queue")


def generate_demo(*args: Any, **kwargs: Any) -> Any:
    raise ExcludedOperationError("Slice A exclusion: no_demo_generation")
