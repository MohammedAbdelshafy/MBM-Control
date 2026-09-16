"""Base builder interface for concrete product materialization."""

from __future__ import annotations
from typing import Any, Protocol

from MBM.DemandFactory.compiler import BuildPlan

class BuilderInterface(Protocol):
    """Interface for all Digital Product Builders."""
    
    def can_build(self, plan: BuildPlan) -> bool:
        """Returns True if the builder can satisfy the BuildPlan capabilities."""
        ...
        
    def execute(self, plan: BuildPlan) -> dict[str, Any]:
        """Executes the BuildPlan deterministically."""
        ...
        
    def rollback(self, plan: BuildPlan) -> bool:
        """Executes rollback steps for a given BuildPlan."""
        ...
