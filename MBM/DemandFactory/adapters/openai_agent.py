"""OpenAI Agents SDK adapter for bounded agent tasks."""

from __future__ import annotations
from typing import Any

from MBM.DemandFactory.adapters.builder import BuilderInterface
from MBM.DemandFactory.compiler import BuildPlan

class OpenAIAgentAdapter(BuilderInterface):
    """Adapter for executing BuildPlans via the OpenAI Agents SDK."""
    
    SUPPORTED_CAPABILITIES = {
        "content_generation",
        "data_enrichment",
        "email_drafting",
        "ui_generation"
    }

    def can_build(self, plan: BuildPlan) -> bool:
        """Checks if this adapter supports the requested capabilities."""
        # The compile phase resolved the capabilities. For this simple stub,
        # we check if any steps attempt actions not supported by this agent.
        for step in plan.steps:
            if step.get("action") == "provision_capabilities":
                for cap in step.get("capabilities", []):
                    if cap not in self.SUPPORTED_CAPABILITIES:
                        return False
        return True
        
    def execute(self, plan: BuildPlan) -> dict[str, Any]:
        """Executes the BuildPlan using the bounded Agent adapter."""
        if not self.can_build(plan):
            raise ValueError(f"OpenAIAgentAdapter cannot build plan {plan.plan_id}: Unsupported capabilities.")
            
        results = {
            "plan_id": plan.plan_id,
            "status": "dry_run" if plan.is_dry_run else "completed",
            "materialized_assets": []
        }
        
        for step in plan.steps:
            # Simulate materialization
            if step.get("action") == "materialize_deliverables":
                for deliverable in step.get("deliverables", []):
                    results["materialized_assets"].append(
                        f"stub_asset_for_{deliverable}"
                    )
                    
        return results

    def rollback(self, plan: BuildPlan) -> bool:
        """Simulates rollback of materialized assets."""
        return True
