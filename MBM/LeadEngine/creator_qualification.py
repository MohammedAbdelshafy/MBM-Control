from __future__ import annotations
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional
from urllib.parse import urlparse

@dataclass
class CreatorRecord:
    creator_id: str
    platform: str
    profile_url: str
    audience_count: int
    audience_type: str
    audience_snapshot_at: str
    evidence_url: str
    evidence_source: str
    niche: str
    contact_path: str
    outreach_status: str
    provenance_key: str
    state: Literal["raw", "qualified", "rejected"] = "raw"
    rejection_reason: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)

def _is_valid_url(url: str) -> bool:
    if not url:
        return False
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

def qualify_creator(creator: CreatorRecord) -> CreatorRecord:
    """Deterministic 20K+ qualification gate for creators."""
    
    now = datetime.now(timezone.utc)
    
    # 1. Audience count
    try:
        count = int(creator.audience_count)
        if count < 20000:
            creator.state = "rejected"
            creator.rejection_reason = "Audience count below 20,000 threshold"
            return creator
    except (ValueError, TypeError):
        creator.state = "rejected"
        creator.rejection_reason = "Malformed audience count"
        return creator

    # 2. Evidence validation
    if not _is_valid_url(creator.evidence_url):
        creator.state = "rejected"
        creator.rejection_reason = "Missing or malformed evidence URL"
        return creator

    # 3. Profile validation
    if not _is_valid_url(creator.profile_url):
        creator.state = "rejected"
        creator.rejection_reason = "Missing or malformed profile URL"
        return creator
        
    if not creator.platform or len(creator.platform) < 2:
        creator.state = "rejected"
        creator.rejection_reason = "Malformed platform"
        return creator

    # 4. Evidence freshness
    try:
        # Handle trailing Z
        ts = creator.audience_snapshot_at.replace("Z", "+00:00")
        snapshot_time = datetime.fromisoformat(ts)
        if snapshot_time.tzinfo is None:
            snapshot_time = snapshot_time.replace(tzinfo=timezone.utc)
            
        days_old = (now - snapshot_time).days
        if days_old > 30:
            creator.state = "rejected"
            creator.rejection_reason = "Stale evidence (older than 30 days)"
            return creator
    except (ValueError, TypeError):
        creator.state = "rejected"
        creator.rejection_reason = "Malformed audience_snapshot_at"
        return creator

    # 5. Provenance validation
    if not creator.provenance_key or len(creator.provenance_key) < 5:
        creator.state = "rejected"
        creator.rejection_reason = "Invalid provenance key"
        return creator

    creator.state = "qualified"
    return creator
