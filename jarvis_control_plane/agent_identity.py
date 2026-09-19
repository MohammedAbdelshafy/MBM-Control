"""Provider-neutral agent identity contract.

Inspired by Google Agent Identity: every capability-gated invocation can be
attributed to a stable agent principal with explicit capabilities and scopes.
This module is local and provider-neutral; it does not mint cloud identities
or manage credentials.
"""

from __future__ import annotations

from typing import Dict, List

from pydantic import BaseModel, Field


class IdentityDenied(PermissionError):
    """Raised when an agent identity cannot be established."""


class AgentIdentity(BaseModel):
    """Stable identity metadata used by the local control plane."""

    agent_id: str
    capabilities: List[str] = Field(default_factory=list)
    read_scope: List[str] = Field(default_factory=list)
    write_scope: List[str] = Field(default_factory=list)
    metadata: Dict[str, str] = Field(default_factory=dict)

    def has_capability(self, capability: str) -> bool:
        return capability in self.capabilities


class AgentIdentityRegistry:
    """In-memory registry for trusted agent identities.

    Persistence belongs to the caller so this registry cannot silently become
    a second source of truth.
    """

    def __init__(self) -> None:
        self._identities: Dict[str, AgentIdentity] = {}

    def register(self, identity: AgentIdentity) -> None:
        if not identity.agent_id.strip():
            raise IdentityDenied("agent_id must be non-empty")
        self._identities[identity.agent_id] = identity

    def get(self, agent_id: str) -> AgentIdentity:
        require_identity(agent_id)
        try:
            return self._identities[agent_id]
        except KeyError as exc:
            raise IdentityDenied(f"unknown agent identity: {agent_id}") from exc

    def has(self, agent_id: str) -> bool:
        try:
            self.get(agent_id)
        except IdentityDenied:
            return False
        return True

    def require_capability(self, agent_id: str, capability: str) -> AgentIdentity:
        identity = self.get(agent_id)
        if not capability or not identity.has_capability(capability):
            raise IdentityDenied(
                f"agent '{agent_id}' lacks required capability '{capability}'"
            )
        return identity


def require_identity(agent_id: str | None) -> str:
    if not isinstance(agent_id, str) or not agent_id.strip():
        raise IdentityDenied("agent identity is required")
    return agent_id.strip()
