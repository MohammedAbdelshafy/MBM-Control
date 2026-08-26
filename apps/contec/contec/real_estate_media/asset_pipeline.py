"""REAL_ESTATE_PROPERTY_VIDEO_FACTORY pipeline (pure logic).

Stages: LISTING_DISCOVERED -> IMAGES_COLLECTED -> ASSET_VALIDATED ->
        VIDEO_PROMPT_GENERATED -> AI_VIDEO_RENDER -> QUALITY_CHECK ->
        SAMPLE_READY -> DELIVERY_READY

Facts-only law: the generated prompt describes ONLY supplied listing facts.
No invented features. Corrupt/low-quality/duplicate assets are rejected with
reasons; provenance is carried end-to-end.
"""
from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional, Tuple

PIPELINE_STAGES = [
    "LISTING_DISCOVERED", "IMAGES_COLLECTED", "ASSET_VALIDATED",
    "VIDEO_PROMPT_GENERATED", "AI_VIDEO_RENDER", "QUALITY_CHECK",
    "SAMPLE_READY", "DELIVERY_READY",
]

CATEGORY_ORDER = ["exterior", "living", "kitchen", "bedroom", "bathroom",
                  "amenity", "lifestyle"]

MIN_DIMENSION = 640          # reject below this width/height
MIN_BYTES = 30_000           # reject tiny/corrupt payloads


def _asset_id(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def validate_assets(images: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """images: [{bytes|size, width, height, category?, source_url?}] ->
    (accepted[], rejected[]) with reasons. Duplicate hashes dropped."""
    accepted: List[Dict[str, Any]] = []
    rejected: List[Dict[str, Any]] = []
    seen_hashes = set()
    for idx, img in enumerate(images):
        size = int(img.get("size") or len(img.get("bytes") or b"") or 0)
        w = int(img.get("width") or 0)
        h = int(img.get("height") or 0)
        if size < MIN_BYTES:
            rejected.append({"index": idx, "reason": "corrupt_or_tiny_payload"})
            continue
        if w < MIN_DIMENSION or h < MIN_DIMENSION:
            rejected.append({"index": idx, "reason": "low_resolution",
                             "detail": f"{w}x{h}"})
            continue
        digest = img.get("sha256_16") or _asset_id(img.get("bytes") or str(idx).encode())
        if digest in seen_hashes:
            rejected.append({"index": idx, "reason": "duplicate_asset"})
            continue
        seen_hashes.add(digest)
        accepted.append({**img, "sha256_16": digest,
                         "category": (img.get("category") or "lifestyle").lower()})
    return accepted, rejected


def sequence_assets(accepted: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Exterior-first tour order; stable within category."""
    rank = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    return sorted(accepted, key=lambda a: rank.get(a.get("category"), 99))


def build_prompt(listing: Dict[str, Any], sequenced: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Cinematic prompt from FACTS ONLY."""
    beds = listing.get("bedrooms")
    baths = listing.get("bathrooms")
    city = listing.get("city")
    facts: List[str] = []
    if beds:
        facts.append(f"{beds} bedroom")
    if baths:
        facts.append(f"{baths} bathroom")
    cats = sorted({a["category"] for a in sequenced})
    if cats:
        facts.append("featuring " + ", ".join(cats))
    if city:
        facts.append(f"located in {city}")
    prompt = (
        f"Cinematic real-estate property tour: smooth gimbal-style walkthrough, "
        f"natural daylight, elegant pacing. Property is a {', '.join(facts) or 'residential home'}. "
        f"Show only the provided photographs as scenes in order; no invented rooms, "
        f"no fabricated features, factual on-screen text limited to supplied metadata."
    )
    return {"prompt": prompt, "fact_basis": [f for f in (beds and f"beds={beds}", baths and f"baths={baths}", city) if f],
            "scene_count": len(sequenced)}


def aspect_plan(short_form: bool = True) -> List[Dict[str, str]]:
    plan = [{"ratio": "9:16", "purpose": "reels/shorts"},
            {"ratio": "16:9", "purpose": "portal/website"}]
    if short_form:
        plan.append({"ratio": "1:1", "purpose": "feed"})
    return plan


def next_stage(current: str) -> Optional[str]:
    try:
        i = PIPELINE_STAGES.index(current)
    except ValueError:
        raise ValueError(f"unknown stage {current!r}")
    return PIPELINE_STAGES[i + 1] if i + 1 < len(PIPELINE_STAGES) else None
