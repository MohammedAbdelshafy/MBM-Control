"""Digital Product Compiler (#59)

The governed front door for generated products. Takes a ProductSpec IR, validates it,
and produces a deterministic BuildPlan + canonical plan hash.
No arbitrary LLM-generated runtime code and no autonomous production release.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Literal

@dataclass(slots=True)
class ProductSpec:
    spec_version: str
    product_id: str
    target_market: str
    deliverables: list[str]
    capabilities: list[str]
    permissions_required: list[str]
    dependencies: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

@dataclass(slots=True)
class BuildPlan:
    plan_id: str
    product_id: str
    plan_hash: str
    is_dry_run: bool
    steps: list[dict[str, Any]]
    permissions_granted: list[str]
    rollback_steps: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

class ValidationFailure(Exception):
    pass

class ProductCompiler:
    """Compiles a ProductSpec into a BuildPlan deterministically."""
    
    ALLOWED_CAPABILITIES = {
        "content_generation",
        "data_enrichment",
        "email_drafting",
        "ui_generation"
    }
    
    UNSAFE_PERMISSIONS = {
        "production_database_write",
        "live_payment_capture",
        "autonomous_outbound_sending"
    }

    def compile(self, spec: ProductSpec, *, dry_run: bool = True) -> BuildPlan:
        """Validates spec and produces a deterministic BuildPlan."""
        # 1. Validate Schema and Capabilities
        if spec.spec_version != "1.0":
            raise ValidationFailure(f"Unsupported spec version: {spec.spec_version}")
            
        for cap in spec.capabilities:
            if cap not in self.ALLOWED_CAPABILITIES:
                raise ValidationFailure(f"Unsupported capability requested: {cap}")
                
        # 2. Validate Permissions and Fail Closed on Unsafe Actions
        for perm in spec.permissions_required:
            if perm in self.UNSAFE_PERMISSIONS:
                raise ValidationFailure(f"Unsafe permission requested: {perm}. Autonomous production release blocked.")
        
        # 3. Resolve Dependencies
        resolved_dependencies = sorted(spec.dependencies)
        
        # 4. Produce Deterministic Steps
        steps = [
            {"action": "resolve_dependencies", "items": resolved_dependencies},
            {"action": "provision_capabilities", "capabilities": sorted(spec.capabilities)},
            {"action": "materialize_deliverables", "deliverables": sorted(spec.deliverables)},
        ]
        
        rollback_steps = [
            {"action": "revoke_capabilities", "capabilities": sorted(spec.capabilities)},
            {"action": "clean_materialized_artifacts"},
        ]
        
        # 5. Generate Canonical Plan Hash
        plan_content = json.dumps(
            {
                "product_id": spec.product_id,
                "steps": steps,
                "permissions": sorted(spec.permissions_required),
                "is_dry_run": dry_run
            },
            sort_keys=True
        )
        plan_hash = hashlib.sha256(plan_content.encode("utf-8")).hexdigest()
        
        return BuildPlan(
            plan_id=f"plan_{plan_hash[:12]}",
            product_id=spec.product_id,
            plan_hash=plan_hash,
            is_dry_run=dry_run,
            steps=steps,
            permissions_granted=sorted(spec.permissions_required),
            rollback_steps=rollback_steps,
        )
