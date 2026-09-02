"""Dry-Run Campaign Representation.

Creates a complete representation of what a campaign would do:
- channel
- content asset
- title / description / tags
- privacy status (TEST / PRIVATE / PUBLIC — BLOCKED by default for production)
- scheduled time
- thumbnail reference
- idempotency key
- expected quota cost

No uploads. No publishes. No mutations.
"""
from __future__ import annotations
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime


@dataclass(frozen=True)
class DryRunResult:
    idempotency_key: str
    campaign_id: str
    channel_id: str
    video_path: Optional[str]
    title: str
    description: str
    tags: List[str]
    privacy_status: str  # "private" | "unlisted" | "public" (BLOCKED by default)
    scheduled_time: Optional[str]
    thumbnail_ref: Optional[str]
    expected_quota_cost: int
    would_upload: bool
    upload_blocked_reason: Optional[str]
    publish_enabled: bool
    dry_run_timestamp: str
    channel_health_at_run: Optional[str]


class DryRunCampaign:
    """Build and represent a dry-run campaign."""

    def __init__(self):
        pass

    def build(
        self,
        campaign_id: str,
        video_path: Optional[str],
        title: str,
        description: str,
        tags: List[str],
        privacy_status: str = "private",
        scheduled_time: Optional[str] = None,
        thumbnail_ref: Optional[str] = None,
        channel_id: str = "",
    ) -> DryRunResult:
        # M-022 policy: production uploads BLOCKED by default
        # Only TEST/PRIVATE allowed without explicit activation gate
        allowed_privacies = {"private", "unlisted", "public"}
        if privacy_status not in allowed_privacies:
            privacy_status = "private"

        # Upload blocked for production (public) unless gate explicitly activates
        upload_blocked_reason = None
        would_upload = True
        publish_enabled = False  # BLOCKED by default for M-022 readiness

        if privacy_status == "public":
            would_upload = False
            upload_blocked_reason = "M-022 readiness gate: public uploads BLOCKED until READY_FOR_CONTROLLED_ACTIVATION"
            publish_enabled = False

        # Idempotency key based on campaign + asset + scheduled time
        idempotency_key = f"{campaign_id}:{video_path or ''}:{title}:{scheduled_time or ''}"

        return DryRunResult(
            idempotency_key=idempotency_key,
            campaign_id=campaign_id,
            channel_id=channel_id,
            video_path=video_path,
            title=title,
            description=description,
            tags=tags,
            privacy_status=privacy_status,
            scheduled_time=scheduled_time,
            thumbnail_ref=thumbnail_ref,
            expected_quota_cost=1600,  # Reference quota_guard default
            would_upload=would_upload,
            upload_blocked_reason=upload_blocked_reason,
            publish_enabled=publish_enabled,
            dry_run_timestamp=datetime.now().isoformat(),
            channel_health_at_run=None,  # Filled by caller
        )
