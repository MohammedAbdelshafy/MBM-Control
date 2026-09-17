from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class KnowledgeGraphAdapter(Protocol):
    def record_relationships(self, opportunity_id: str, relationships: list[dict[str, str]]) -> dict[str, Any]: ...

    def lookup_context(self, opportunity_id: str) -> dict[str, Any]: ...


def _validate_relationships(relationships: list[dict[str, str]]) -> None:
    required = {"source", "target", "description"}
    for relationship in relationships:
        if not required.issubset(relationship):
            raise ValueError("relationship requires source, target, description")
        if not relationship["source"].strip() or not relationship["target"].strip():
            raise ValueError("relationship source and target must be non-empty")


@dataclass(slots=True)
class NullKnowledgeGraphAdapter:
    """Safe no-op adapter used until a real graph connector is configured."""

    def record_relationships(self, opportunity_id: str, relationships: list[dict[str, str]]) -> dict[str, Any]:
        _validate_relationships(relationships)
        return {"status": "proposed", "opportunity_id": opportunity_id, "relationship_count": len(relationships)}

    def lookup_context(self, opportunity_id: str) -> dict[str, Any]:
        return {"status": "empty", "opportunity_id": opportunity_id, "context": {}}
