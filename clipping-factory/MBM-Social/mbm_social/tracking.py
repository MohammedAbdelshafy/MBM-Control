"""
tracking -- ContentRewards + Neteller attribution for the unified revenue stack.

This module is the BRIDGE between:

  CLIPPING FACTORY (content production)
    -> MBM SOCIAL (distribution)
    -> CONTENTREWARDS (monetization)
    -> ANALYTICS / ROI (measurement)

Every piece of content gets a deterministic, inspectable identity that travels
the entire lifecycle:

  content_id   -- factory campaign_id (e.g. TR-1922-B02CE02259AB, CD-2026-CUTE002)
  brand        -- brand slug (cutedosage, twistsrevealed, etc.)
  source       -- source_identifier / source_uri
  clip_id      -- artifact_dir basename
  platform     -- youtube / tiktok / instagram
  channel      -- YouTube channel_id
  campaign     -- ContentRewards campaign_id (if eligible) or factory campaign_id
  tracking_id  -- deterministic hash of content_id+brand+platform+campaign
  publish_id   -- YouTube video_id (after publish)
  tracking_link -- ContentRewards URL with UTM + tracking_id
  neteller_link -- 1-click payout link (canonical rail)
  status       -- draft | published | verified | etc.
  timestamps   -- created_at, published_at, verified_at

Attribution is deterministic: same content_id always yields same tracking_id
and tracking_link. No fabricated clicks/conversions/revenue; ledger rows are
only updated with platform-reported numbers via record_verification().

Security: never logs secrets, never stores refresh_token/access_token.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Neteller canonical rail (via MBM/Scripts/neteller_config.py) -- fallback if
# that module is unavailable.
# ---------------------------------------------------------------------------

try:
    sys.path.insert(0, str(ROOT.parents[1]))
    from MBM.Scripts.neteller_config import neteller_link as _neteller_link
    from MBM.Scripts.neteller_config import NETELLER_EMAIL, NETELLER_ACCOUNT_ID

    def neteller_link_for_campaign(brand: str, campaign_id: str, amount: float = 47.00) -> str:
        # Map brand/campaign to a sensible default amount/item if not specified
        item_map = {
            "cutedosage": "CuteDosage_ContentRewards_Payout",
            "twistsrevealed": "TwistsRevealed_ContentRewards_Payout",
            "dontwatchthis": "DontWatchThis_Payout",
            "goalmachinez": "GoalMachinez_Payout",
            "clippingfactorymbm": "ClippingFactoryMBM_Payout",
        }
        item = f"{item_map.get(brand, 'Content_Payout')}_{campaign_id[:8]}"
        return _neteller_link(amount=amount, item=item)

except Exception:
    NETELLER_EMAIL = "abdelshafyclapps@gmail.com"
    NETELLER_ACCOUNT_ID = "4599228811"

    def neteller_link_for_campaign(brand: str, campaign_id: str, amount: float = 47.00) -> str:
        base = "https://member.neteller.com/pay"
        params = urlencode({
            "email": NETELLER_EMAIL,
            "account": NETELLER_ACCOUNT_ID,
            "amount": f"{float(amount):.2f}",
            "currency": "USD",
            "item": f"{brand}_{campaign_id[:8]}",
        })
        return f"{base}?{params}"


# ---------------------------------------------------------------------------
# ContentRewards campaign registry
# ---------------------------------------------------------------------------

def _load_contentrewards_campaigns() -> Dict[str, dict]:
    """Load ContentRewards campaigns from Brands/*/campaigns/*.json."""
    campaigns = {}
    brands_dir = ROOT / "Brands"
    if not brands_dir.exists():
        return campaigns
    for brand_dir in brands_dir.iterdir():
        if not brand_dir.is_dir():
            continue
        camp_dir = brand_dir / "campaigns"
        if not camp_dir.exists():
            continue
        for f in camp_dir.glob("*.json"):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                cid = data.get("campaign_id") or data.get("id") or f.stem
                brand = data.get("channel", {}).get("brand") or brand_dir.name
                campaigns[cid] = data
                # also index by brand for easy lookup
                campaigns[f"{brand}:{cid}"] = data
            except Exception:
                continue
    return campaigns


_CONTENTREWARDS_CACHE: Optional[Dict[str, dict]] = None


def get_contentrewards_campaign(campaign_id: str, brand: str = "") -> Optional[dict]:
    global _CONTENTREWARDS_CACHE
    if _CONTENTREWARDS_CACHE is None:
        _CONTENTREWARDS_CACHE = _load_contentrewards_campaigns()
    # direct hit
    if campaign_id in _CONTENTREWARDS_CACHE:
        return _CONTENTREWARDS_CACHE[campaign_id]
    if brand and f"{brand}:{campaign_id}" in _CONTENTREWARDS_CACHE:
        return _CONTENTREWARDS_CACHE[f"{brand}:{campaign_id}"]
    # brand-only lookup: return first campaign for that brand (e.g. cutedosage)
    if brand:
        for k, v in _CONTENTREWARDS_CACHE.items():
            if ":" in k and k.startswith(f"{brand}:"):
                return v
    return None


def _contentrewards_campaign_for_brand(brand: str) -> Optional[dict]:
    """Return the ContentRewards campaign associated with a brand, if any."""
    # Currently only cutedosage has a real ContentRewards campaign
    # (My Mini Mom & Baby). For other brands, return None -> Neteller-only.
    if brand.lower() == "cutedosage":
        return get_contentrewards_campaign("c1ef50c5-b0f7-4b23-bdbe-1fc33a965935", brand)
    return None


# ---------------------------------------------------------------------------
# Deterministic tracking identity
# ---------------------------------------------------------------------------

def generate_tracking_id(content_id: str, brand: str, platform: str, campaign_id: str) -> str:
    """Deterministic tracking_id = first 12 hex of sha256(content_id:brand:platform:campaign_id)."""
    raw = f"{content_id}:{brand.lower()}:{platform.lower()}:{campaign_id}"
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


def generate_tracking_link(
    content_id: str,
    brand: str,
    platform: str,
    channel_id: str,
    campaign_id: str,
    source_identifier: str = "",
) -> str:
    """
    Generate ContentRewards-style tracking link.

    For ContentRewards-eligible brands (cutedosage), links to the real
    ContentRewards campaign URL with UTM + tracking_id. For other brands,
    links to a deterministic internal attribution URL that can be resolved
    to the same ledger.

    No secrets, no fabricated clicks.
    """
    tracking_id = generate_tracking_id(content_id, brand, platform, campaign_id)
    cr_campaign = _contentrewards_campaign_for_brand(brand)
    if cr_campaign and cr_campaign.get("campaign_url"):
        base = cr_campaign["campaign_url"]
        # Append UTM + tracking params
        params = {
            "utm_source": brand,
            "utm_medium": platform,
            "utm_campaign": content_id,
            "utm_content": tracking_id,
            "tracking_id": tracking_id,
            "channel": channel_id,
            "source": source_identifier[:32] if source_identifier else "",
        }
        sep = "&" if "?" in base else "?"
        return f"{base}{sep}{urlencode(params)}"
    # Fallback for non-ContentRewards brands: internal attribution link
    # that mirrors the same params but points to our own attribution endpoint
    base = f"https://contentrewards.com/discover/{campaign_id}"
    params = {
        "utm_source": brand,
        "utm_medium": platform,
        "utm_campaign": content_id,
        "utm_content": tracking_id,
        "tracking_id": tracking_id,
        "channel": channel_id,
    }
    return f"{base}?{urlencode(params)}"


def build_tracking_context(package: dict) -> dict:
    """
    Build full tracking context for a publish package.

    Returns dict with content_id, brand, platform, channel, campaign,
    tracking_id, tracking_link, neteller_link, destination, timestamps.

    Deterministic and inspectable; safe to call multiple times (idempotent).
    If package already has a tracking_id/tracking_link, reuse it.
    """
    content_id = package.get("campaign_id") or package.get("id") or package.get("content_id") or "unknown"
    brand = (package.get("brand") or "unknown").strip().lower()
    platform = (package.get("target_platform") or package.get("platform") or "youtube").strip().lower()
    # normalize platform aliases
    if platform in ("youtube_shorts", "youtube_shorts"):
        platform = "youtube"
    if platform == "instagram_reels":
        platform = "instagram"
    channel_id = package.get("youtube_channel_id") or package.get("channel_id") or package.get("channelId") or ""
    # campaign is ContentRewards campaign if brand eligible, else content_id
    cr_campaign = _contentrewards_campaign_for_brand(brand)
    if cr_campaign:
        campaign_id = cr_campaign.get("campaign_id", content_id)
        campaign_name = cr_campaign.get("campaign_name", "")
    else:
        campaign_id = content_id
        campaign_name = package.get("campaign_name") or package.get("title") or ""

    source_identifier = package.get("source_identifier") or package.get("source_id") or ""

    # Idempotent: reuse existing tracking_id/link if already present
    tracking_id = package.get("tracking_id") or generate_tracking_id(content_id, brand, platform, campaign_id)
    tracking_link = package.get("tracking_link") or generate_tracking_link(
        content_id, brand, platform, channel_id, campaign_id, source_identifier
    )
    # Neteller link: amount varies by brand (approximate CPM-derived payout)
    # For ContentRewards, neteller is secondary; for direct monetization, primary.
    neteller_link = package.get("neteller_link") or package.get("neteller_checkout_link")
    if not neteller_link:
        # Use ContentRewards CPM to estimate a sensible Neteller item amount
        # Cut e: $0.80 CPM YouTube, others via Neteller direct
        amount_map = {"cutedosage": 47.00, "twistsrevealed": 47.00, "dontwatchthis": 47.00, "goalmachinez": 47.00, "clippingfactorymbm": 497.00}
        amount = amount_map.get(brand, 47.00)
        neteller_link = neteller_link_for_campaign(brand, campaign_id, amount)

    clip_id = package.get("artifact_id") or (Path(package.get("artifact_dir", "")).name if package.get("artifact_dir") else content_id)
    video_path = package.get("video") or package.get("video_path") or ""

    now_iso = datetime.now(timezone.utc).isoformat()

    context = {
        "content_id": content_id,
        "brand": brand,
        "source": source_identifier,
        "clip_id": clip_id,
        "platform": platform,
        "channel": channel_id,
        "channel_handle": package.get("handle") or package.get("channel_handle") or "",
        "campaign": campaign_id,
        "campaign_name": campaign_name,
        "tracking_id": tracking_id,
        "tracking_link": tracking_link,
        "neteller_link": neteller_link,
        "destination": tracking_link,  # canonical destination for clicks
        "video_path": video_path,
        "status": package.get("status", "draft"),
        "created_at": package.get("created_at") or package.get("packaged_at") or now_iso,
        "updated_at": now_iso,
    }
    return context


def inject_tracking_into_description(package: dict, context: Optional[dict] = None) -> dict:
    """
    Inject tracking links into package description. Idempotent: if tracking
    already present, do not duplicate.

    Returns updated package dict (mutates in place for convenience).
    """
    if context is None:
        context = build_tracking_context(package)

    original_desc = package.get("description") or ""
    tracking_link = context["tracking_link"]
    neteller_link = context["neteller_link"]
    content_id = context["content_id"]

    # Check idempotency: if tracking_id already in description, skip
    if context["tracking_id"] in original_desc or tracking_link in original_desc:
        # Ensure package has tracking fields even if description already injected
        package["tracking_id"] = context["tracking_id"]
        package["tracking_link"] = tracking_link
        package["neteller_link"] = neteller_link
        package["content_id"] = content_id
        return package

    # Build tracking block
    tracking_block = (
        f"\n\n---\n"
        f"🔗 Content ID: {content_id} | Brand: {context['brand']} | Tracking: {context['tracking_id']}\n"
        f"📊 Track this content: {tracking_link}\n"
        f"💰 Support & offers: {neteller_link}\n"
    )
    # For ContentRewards brands, highlight CPM payout
    cr_campaign = _contentrewards_campaign_for_brand(context["brand"])
    if cr_campaign and context["brand"] == "cutedosage":
        cpm = cr_campaign.get("posting_requirements", {}).get("platforms", {}).get("youtube", {}).get("cpm", 0.80)
        tracking_block += f"💸 Earn ${cpm:.2f}/1k views via ContentRewards until ${cr_campaign.get('budget', {}).get('remaining', '?')} remaining\n"

    package["description"] = original_desc.rstrip() + tracking_block
    package["tracking_id"] = context["tracking_id"]
    package["tracking_link"] = tracking_link
    package["neteller_link"] = neteller_link
    package["content_id"] = content_id
    package["campaign"] = context["campaign"]
    package["tracking_context"] = context  # full context for ledger

    # Also set standard attribution fields expected by analytics
    package["tracking_id"] = context["tracking_id"]
    package["campaign"] = context["campaign"]
    package["destination"] = context["destination"]

    return package


def record_publish_event(
    package: dict,
    video_id: str,
    channel_id: str,
    verification: Optional[dict] = None,
) -> dict:
    """
    Build a publish event record that ties content_id -> publish_id -> tracking_id.

    This is the deterministic attribution record used by:
      - ContentRewards ledger (estimated -> verified -> actual)
      - YouTube analytics ledger
      - ROI / learning loop

    No fabricated revenue; actual numbers only come from platform verification.
    """
    context = build_tracking_context(package)
    # Ensure tracking is injected (idempotent)
    inject_tracking_into_description(package, context)

    event = {
        "content_id": context["content_id"],
        "brand": context["brand"],
        "source": context["source"],
        "clip_id": context["clip_id"],
        "platform": context["platform"],
        "channel": channel_id or context["channel"],
        "channel_handle": context["channel_handle"],
        "campaign": context["campaign"],
        "campaign_name": context["campaign_name"],
        "tracking_id": context["tracking_id"],
        "tracking_link": context["tracking_link"],
        "neteller_link": context["neteller_link"],
        "destination": context["destination"],
        "publish_id": video_id,
        "video_id": video_id,
        "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else "",
        "status": "published",
        "published_at": datetime.now(timezone.utc).isoformat(),
        "verification": verification or {},
        # Revenue placeholders -- filled by analytics, never invented
        "clicks": None,
        "conversions": None,
        "revenue": None,
        "verified_views": None,
        "actual_revenue_usd": None,
    }
    return event


# ---------------------------------------------------------------------------
# Helpers for ledger integration
# ---------------------------------------------------------------------------

def package_to_content_rewards_campaign(package: dict):
    """Convert a factory/MBM package to a ContentRewards Campaign object."""
    try:
        from .content_rewards import normalize_campaign
    except ImportError:
        return None
    ctx = build_tracking_context(package)
    raw = {
        "brand": ctx["brand"],
        "topic": package.get("niche") or package.get("theme") or package.get("tags", [""])[0] if package.get("tags") else "general",
        "title": package.get("title", ""),
        "hook": package.get("title", "")[:80],
        "source_url": package.get("source_uri") or "",
        "transcript_snippet": package.get("description", "")[:120],
        "timestamp_accuracy": 1.0 if ctx["source"] else 0.0,
        "hook_score": 0.8,
        "estimated_duration_s": 55,
        "target_platform": ctx["platform"],
        "production_minutes": 20.0,
        "id": ctx["content_id"],
        "asset_id": ctx["clip_id"],
    }
    # Clean topic
    topic = str(raw["topic"]).lower().strip()
    if not topic or topic in ("", "general", "us"):
        # Use brand-appropriate default
        defaults = {
            "cutedosage": "cute",
            "twistsrevealed": "plot twist",
            "dontwatchthis": "mystery",
            "goalmachinez": "football",
            "clippingfactorymbm": "automation",
        }
        raw["topic"] = defaults.get(ctx["brand"], "general")
    try:
        return normalize_campaign(raw)
    except Exception:
        return None
