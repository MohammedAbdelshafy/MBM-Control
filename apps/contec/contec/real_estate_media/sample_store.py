"""GENERATE_PROPERTY_SAMPLE record builder.

Samples link 1:1 to (agent, listing); duplicates blocked. QA gate required
before DELIVERY_READY. Provenance stored end-to-end.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from . import asset_pipeline as ap
from .providers import get_provider


def build_sample_record(agent: Dict[str, Any], listing: Dict[str, Any],
                        images: List[Dict[str, Any]], *,
                        provider_code: Optional[str] = None,
                        settings: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    accepted, rejected = ap.validate_assets(images)
    if not accepted:
        return {"generation_status": "BLOCKED", "block_reason": "no_valid_assets",
                "rejected": rejected}
    sequenced = ap.sequence_assets(accepted)
    prompt = ap.build_prompt(listing, sequenced)
    provider = get_provider(provider_code or (settings or {}).get("video_provider"))

    record: Dict[str, Any] = {
        "listing_id": listing.get("listing_id"),
        "agent_id": agent.get("agent_id") or agent.get("name"),
        "source_url": listing.get("source_url"),
        "source_images": [
            {"sha256_16": a.get("sha256_16"), "category": a.get("category"),
             "source_url": a.get("source_url")}
            for a in sequenced
        ],
        "rejected_assets": rejected,
        "prompt": prompt["prompt"],
        "aspect_plan": ap.aspect_plan(),
        "provider": provider.code,
        "generation_status": "PENDING",
        "qa_status": "NOT_RUN",
        "delivery_status": "NOT_DELIVERED",
    }

    if not provider.available():
        record["generation_status"] = "SKIPPED_UNAVAILABLE"
        record["provider_error"] = "provider_not_configured"
        return record

    result = provider.render(prompt=prompt["prompt"], images=sequenced,
                             aspects=record["aspect_plan"])
    record["model"] = result.get("model")
    record["outputs"] = result.get("outputs", [])
    if result["status"] == "SUCCEEDED":
        qa = provider.qa_check(record["outputs"])
        record["qa_status"] = qa["qa_status"]
        record["generation_status"] = "SUCCEEDED"
        if qa["qa_status"] == "PASS":
            record["pipeline_stage"] = "SAMPLE_READY"
            # delivery only after human approval flag (settings gate)
            if (settings or {}).get("auto_deliver_samples"):
                record["delivery_status"] = "READY"
        else:
            record["generation_status"] = "QA_FAILED"
            record["qa_missing_aspects"] = qa["missing_aspects"]
    else:
        record["generation_status"] = result["status"]
        record["provider_error"] = result.get("error")
    return record


def is_duplicate_sample(existing: List[Dict[str, Any]], listing_id: Any,
                        agent_id: Any) -> bool:
    return any(
        str(s.get("listing_id")) == str(listing_id)
        and str(s.get("agent_id")) == str(agent_id)
        and s.get("generation_status") in ("SUCCEEDED", "PENDING")
        for s in existing
    )


def generation_limit_reached(existing_for_agent: int,
                             settings: Optional[Dict[str, Any]] = None) -> bool:
    limit = int((settings or {}).get("max_auto_samples_per_agent", 1))
    return existing_for_agent >= limit
