"""
Client campaign mode — Phase 11 (INTERNAL_BRAND vs CLIENT_CAMPAIGN).

Same factories, different configuration. This module validates client campaign
configuration and exposes the distinct client fields required by the mission.
It does NOT touch the rendering factories — it is a configuration contract that
downstream stages (intake, approval, delivery, KPI tracking) consume.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

INTERNAL = "INTERNAL_BRAND"
CLIENT = "CLIENT_CAMPAIGN"


@dataclass
class CampaignConfig:
    kind: str = INTERNAL
    campaign_id: str = ""
    brand: str = ""
    # Client-only fields (ignored for INTERNAL)
    client: str = ""
    source_ownership_confirmed: bool = False
    output_quantity: int = 0
    target_platforms: list[str] = field(default_factory=list)
    brand_assets: dict = field(default_factory=dict)
    delivery_sla_hours: int = 0
    approval_mode: str = "auto"          # "auto" | "per_clip" | "batch"
    revisions_allowed: int = 0
    kpi_targets: dict = field(default_factory=dict)
    quality_gate: float = 0.65

    def to_dict(self) -> dict:
        return {
            "kind": self.kind, "campaign_id": self.campaign_id, "brand": self.brand,
            "client": self.client, "source_ownership_confirmed": self.source_ownership_confirmed,
            "output_quantity": self.output_quantity, "target_platforms": self.target_platforms,
            "brand_assets": self.brand_assets, "delivery_sla_hours": self.delivery_sla_hours,
            "approval_mode": self.approval_mode, "revisions_allowed": self.revisions_allowed,
            "kpi_targets": self.kpi_targets, "quality_gate": self.quality_gate,
        }


def from_dict(d: dict) -> CampaignConfig:
    return CampaignConfig(
        kind=d.get("kind", INTERNAL), campaign_id=d.get("campaign_id", ""),
        brand=d.get("brand", ""), client=d.get("client", ""),
        source_ownership_confirmed=bool(d.get("source_ownership_confirmed", False)),
        output_quantity=int(d.get("output_quantity", 0)),
        target_platforms=d.get("target_platforms", []), brand_assets=d.get("brand_assets", {}),
        delivery_sla_hours=int(d.get("delivery_sla_hours", 0)),
        approval_mode=d.get("approval_mode", "auto"),
        revisions_allowed=int(d.get("revisions_allowed", 0)),
        kpi_targets=d.get("kpi_targets", {}), quality_gate=float(d.get("quality_gate", 0.65)),
    )


def validate(cfg: CampaignConfig) -> list[str]:
    """Return a list of human-readable config errors (empty = valid)."""
    errors: list[str] = []
    if not cfg.campaign_id:
        errors.append("campaign_id is required")
    if not cfg.brand:
        errors.append("brand is required")
    if cfg.kind == CLIENT:
        if not cfg.client:
            errors.append("CLIENT_CAMPAIGN requires 'client'")
        if not cfg.source_ownership_confirmed:
            errors.append("CLIENT_CAMPAIGN requires source_ownership_confirmed=true "
                          "(rights/ownership must be confirmed before processing)")
        if cfg.output_quantity <= 0:
            errors.append("CLIENT_CAMPAIGN requires output_quantity > 0")
        if not cfg.target_platforms:
            errors.append("CLIENT_CAMPAIGN requires target_platforms")
        if cfg.approval_mode not in ("auto", "per_clip", "batch"):
            errors.append("approval_mode must be auto|per_clip|batch")
        # quality gate for clients is stricter
        if cfg.quality_gate < 0.70:
            errors.append("CLIENT_CAMPAIGN quality_gate must be >= 0.70")
    return errors
