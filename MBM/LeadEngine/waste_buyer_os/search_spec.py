"""Generate deterministic search briefs for Dawar, Clay and web research."""

from __future__ import annotations

from dataclasses import asdict

from .materials import buyer_categories_for, normalize_material
from .models import FactoryWasteQuota


DAWAR_MARKETPLACE_URL = "https://dawarapp.com/marketplace/"


def build_search_spec(quota: FactoryWasteQuota) -> dict:
    errors = quota.validate()
    if errors:
        raise ValueError("; ".join(errors))

    material = normalize_material(quota.material)
    material_text = material.replace("_", " ")
    categories = buyer_categories_for(material)
    location = quota.geography or "Egypt"

    queries = [f'{category} "{material_text}" Egypt' for category in categories]
    queries += [
        f'"{material_text}" recycler Egypt buyer',
        f'"{material_text}" recycling facility Egypt',
    ]

    return {
        "source_rail": {
            "name": "Dawar",
            "marketplace_url": DAWAR_MARKETPLACE_URL,
            "role": "marketplace/network for verified recyclers and buyers",
        },
        "quota": asdict(quota),
        "material_canonical": material,
        "buyer_categories": list(categories),
        "web_queries": queries,
        "qualification_checks": [
            "company identity and website",
            "public evidence that the buyer processes or purchases this material",
            "accepted material/form/grade",
            "collection radius or delivered logistics",
            "monthly purchasing capacity or MOQ, when disclosed",
            "decision-maker role for commercial discussion",
            "sample/inspection requirements",
        ],
        "disposition_rule": (
            "Do not mark a buyer qualified from a directory name alone. "
            "Require public evidence and then confirm acceptance, logistics, and quota."
        ),
        "compliance_note": (
            "Keep finished branded/counterfeit footwear separate from material scrap. "
            "Prioritize unbranded/OEM scrap and recyclable components unless lawful disposition is confirmed."
        ),
        "location": location,
    }
