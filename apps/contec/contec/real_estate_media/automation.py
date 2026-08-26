"""Observable, restartable acquisition loop.

DISCOVER -> QUALIFY -> SELECT LISTING -> GENERATE SAMPLE -> QA ->
ADD TO DIALER -> ... Every unit of work flows through an injectable
queue/store interface; failures land in a retry/error queue - never silent.

Frappe integration wraps these functions with `frappe.enqueue` + real docsets;
the pure orchestrator below is hermetically testable.
"""
from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional


class WorkQueue:
    """Minimal restartable queue with retry/error lanes."""

    def __init__(self, max_attempts: int = 3):
        self.pending: List[Dict[str, Any]] = []
        self.retry: List[Dict[str, Any]] = []
        self.dead: List[Dict[str, Any]] = []
        self.done: List[Dict[str, Any]] = []
        self.max_attempts = max_attempts

    def push(self, item: Dict[str, Any]) -> None:
        self.pending.append({**item, "attempts": 0})

    def process(self, handler: Callable[[Dict[str, Any]], Any]) -> Dict[str, int]:
        i = 0
        while i < len(self.pending):
            item = self.pending[i]
            try:
                handler(item)
                item["result"] = "ok"
                self.done.append(item)
                self.pending.pop(i)
            except Exception as exc:  # noqa: BLE001 - queue boundary records all
                item["attempts"] = int(item.get("attempts", 0)) + 1
                item["last_error"] = str(exc)[:200]
                self.pending.pop(i)
                if item["attempts"] >= self.max_attempts:
                    self.dead.append(item)
                else:
                    self.retry.append(item)
        return {"done": len(self.done), "retry": len(self.retry),
                "dead": len(self.dead), "pending": len(self.pending)}

    def requeue_retries(self) -> int:
        n = len(self.retry)
        self.pending = self.retry + self.pending
        self.retry = []
        return n


def qualify_and_route(agent: Dict[str, Any], *,
                      settings: Dict[str, Any],
                      existing_agents: List[Dict[str, Any]],
                      enqueue_dialer: Callable[[Dict[str, Any]], None]) -> Dict[str, Any]:
    """One agent's path through QUALIFY -> (SAMPLE) -> ADD TO DIALER."""
    from .lead_dedup import find_duplicate
    from .scoring import real_estate_media_score

    dup = find_duplicate(agent, existing_agents)
    if dup:
        return {"routed": False, "reason": "duplicate_of:" + str(dup.get("name") or dup.get("agent_id"))}

    score = real_estate_media_score(agent)
    min_qual = int(settings.get("min_qualification_score", 45))
    if score["score"] < min_qual:
        return {"routed": False, "reason": f"below_threshold:{score['score']}<{min_qual}",
                "score": score}

    payload = {**agent, "qualification_score": score["score"], "tier": score["tier"]}
    if agent.get("sample_url"):
        payload["sample_available"] = True
    enqueue_dialer(payload)
    return {"routed": True, "score": score}
