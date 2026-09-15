from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(slots=True)
class CreativeAssetSpec:
    asset_type: str
    job_to_be_done: str
    claim_or_outcome: str
    format: str
    channel: str
    prompt_brief: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_creative_plan(product_name: str, buyer_segment: str, outcome: str) -> list[CreativeAssetSpec]:
    """Return a reusable creative brief for Higgsfield production."""
    context = f"{product_name} for {buyer_segment}, outcome: {outcome}"
    return [
        CreativeAssetSpec("hero", "make the outcome immediately legible", outcome, "16:9", "landing_page", f"Premium product hero showing {context}; tangible interface/product, clean lighting, no fake testimonial text."),
        CreativeAssetSpec("demo", "show mechanism and usefulness", outcome, "16:9", "landing_page", f"Screen/product demonstration of {context}; show inputs, process, and output in one visual story."),
        CreativeAssetSpec("proof", "make evidence inspectable", "verified proof", "1:1", "social", f"Evidence-led visual for {context}; show a real artifact, benchmark, workflow, or before/after only when sourced."),
        CreativeAssetSpec("ugc", "answer the first buyer objection", "objection handling", "9:16", "shortform", f"Natural UGC-style explanation of {context}; one objection, one concrete demonstration, one next step; avoid invented results."),
        CreativeAssetSpec("offer_card", "make the buying decision easy to understand", "scope + price + delivery", "1:1", "checkout", f"Clean offer card for {context}; show exactly what is included, price, delivery timing, and terms."),
    ]
