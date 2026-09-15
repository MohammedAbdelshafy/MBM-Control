from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(slots=True)
class HiggsfieldCreativeAdapter:
    """Builds generation briefs; it never submits media jobs itself."""

    def build_asset_plan(self, product_context: dict[str, Any]) -> list[dict[str, Any]]:
        claims = [str(item).strip() for item in product_context.get("claims", []) if str(item).strip()]
        objections = [str(item).strip() for item in product_context.get("objections", []) if str(item).strip()]
        if not claims:
            raise ValueError("creative plan requires at least one product claim")

        assets: list[dict[str, Any]] = []
        assets.append({
            "asset_type": "hero_visual",
            "purpose": "make the promised outcome immediately tangible",
            "claim": claims[0],
            "brief": f"Premium product hero visual demonstrating: {claims[0]}",
        })
        assets.append({
            "asset_type": "product_demo",
            "purpose": "show the mechanism rather than merely describe it",
            "claim": claims[0],
            "brief": f"Crisp demo sequence showing the product delivering: {claims[0]}",
        })
        for index, objection in enumerate(objections[:3], start=1):
            assets.append({
                "asset_type": "objection_visual",
                "purpose": "answer a real buyer hesitation",
                "objection": objection,
                "brief": f"Visual proof that directly addresses buyer objection {index}: {objection}",
            })
        assets.append({
            "asset_type": "social_proof_card",
            "purpose": "surface substantiated evidence",
            "claim": claims[0],
            "brief": "Evidence card using only verified testimonials, benchmarks, demonstrations, or transparent limitations supplied in the product proof inventory.",
        })
        assets.append({
            "asset_type": "ugc_variant",
            "purpose": "provide a natural distribution-native explanation",
            "claim": claims[0],
            "brief": f"Authentic creator-style product explanation focused on the outcome: {claims[0]}",
        })
        return assets
