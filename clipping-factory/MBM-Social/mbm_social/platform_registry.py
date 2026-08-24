"""
Platform capability matrix — the honest source of truth for what each platform
can actually do from this codebase (replaces the fabricated PlatformRegistry).

Status values:
  SUPPORTED          — real, working path exists (YouTube OAuth/API or browser).
  MANUAL_REQUIRED    — a path exists but needs human login/approval/special
                       account status; never auto-faked as Published.
  BLOCKED            — no implementation exists; surfaced as a GitHub issue.

No clip is ever marked Published on a BLOCKED/MANUAL platform without a real
confirmed id. Publishers (post_orchestrator, etc.) MUST consult this module.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

SUPPORTED = "SUPPORTED"
MANUAL_REQUIRED = "MANUAL_REQUIRED"
BLOCKED = "BLOCKED"

# Minimum permissions a GitHub App needs for the control-plane features used.
GITHUB_APP_MIN_PERMISSIONS = {
    "issues": "write",
    "contents": "read",
    "metadata": "read",
    "pull_requests": "write",
}


@dataclass
class PlatformCapability:
    platform: str
    display_name: str
    video_format: str = "9:16"
    max_duration_sec: int = 60
    upload: str = BLOCKED
    publish: str = BLOCKED
    scheduling: str = BLOCKED
    metadata: str = BLOCKED
    thumbnail: str = BLOCKED
    analytics: str = BLOCKED
    api_availability: str = BLOCKED
    credential_requirements: str = "none"
    manual_intervention: str = ""
    notes: str = ""

    @property
    def publish_status(self) -> str:
        """Overall publish readiness: BLOCKED if publish is not possible."""
        if self.publish == BLOCKED:
            return BLOCKED
        if self.publish == MANUAL_REQUIRED:
            return MANUAL_REQUIRED
        return SUPPORTED

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "display_name": self.display_name,
            "video_format": self.video_format,
            "max_duration_sec": self.max_duration_sec,
            "upload": self.upload,
            "publish": self.publish,
            "scheduling": self.scheduling,
            "metadata": self.metadata,
            "thumbnail": self.thumbnail,
            "analytics": self.analytics,
            "api_availability": self.api_availability,
            "credential_requirements": self.credential_requirements,
            "manual_intervention": self.manual_intervention,
            "notes": self.notes,
            "publish_status": self.publish_status,
        }


_CAPS = {
    "youtube": PlatformCapability(
        platform="youtube", display_name="YouTube Shorts", video_format="9:16",
        max_duration_sec=60, upload=SUPPORTED, publish=SUPPORTED,
        scheduling=SUPPORTED, metadata=SUPPORTED, thumbnail=SUPPORTED,
        analytics=MANUAL_REQUIRED, api_availability=SUPPORTED,
        credential_requirements="OAuth client + per-brand refresh token (youtube_tokens.json)",
        manual_intervention="Public publish needs live mode + human-owned channel; "
                            "first upload may trigger account verification.",
        notes="OAuth Data API v3 is the supported path; CDP/Playwright are fallbacks.",
    ),
    "instagram": PlatformCapability(
        platform="instagram", display_name="Instagram Reels", video_format="9:16",
        max_duration_sec=90, upload=MANUAL_REQUIRED, publish=MANUAL_REQUIRED,
        scheduling=MANUAL_REQUIRED, metadata=MANUAL_REQUIRED, thumbnail=MANUAL_REQUIRED,
        analytics=MANUAL_REQUIRED, api_availability=MANUAL_REQUIRED,
        credential_requirements="Instagram Graph API app (Business/Creator account) + token",
        manual_intervention="No Graph API token configured; current path is Playwright "
                            "browser automation which requires a logged-in session.",
        notes="Treat as MANUAL_REQUIRED until a Graph API app + token are provisioned.",
    ),
    "tiktok": PlatformCapability(
        platform="tiktok", display_name="TikTok", video_format="9:16",
        max_duration_sec=600, upload=MANUAL_REQUIRED, publish=MANUAL_REQUIRED,
        scheduling=MANUAL_REQUIRED, metadata=MANUAL_REQUIRED, thumbnail=MANUAL_REQUIRED,
        analytics=MANUAL_REQUIRED, api_availability=MANUAL_REQUIRED,
        credential_requirements="TikTok Content Posting API (audited app) + token",
        manual_intervention="Direct post API requires an audited TikTok app; current path "
                            "is Playwright automation requiring a logged-in session.",
        notes="Treat as MANUAL_REQUIRED until posting API is provisioned.",
    ),
    "linkedin": PlatformCapability(
        platform="linkedin", display_name="LinkedIn Video", video_format="9:16",
        max_duration_sec=600, upload=BLOCKED, publish=BLOCKED,
        scheduling=BLOCKED, metadata=BLOCKED, thumbnail=BLOCKED,
        analytics=BLOCKED, api_availability=BLOCKED,
        credential_requirements="LinkedIn API app + member/org token (NOT implemented)",
        manual_intervention="No LinkedIn publisher exists in this codebase. Requires a "
                            "new implementation + approved API app before it can run.",
        notes="BLOCKED: create a GitHub issue and preserve the package; do not fake publish.",
    ),
    "twitter": PlatformCapability(
        platform="twitter", display_name="Twitter / X Video", video_format="9:16",
        max_duration_sec=140, upload=BLOCKED, publish=BLOCKED,
        scheduling=BLOCKED, metadata=BLOCKED, thumbnail=BLOCKED,
        analytics=BLOCKED, api_availability=BLOCKED,
        credential_requirements="X API v2 with write permission (NOT implemented)",
        manual_intervention="No X/Twitter publisher exists in this codebase. Requires a "
                            "new implementation + approved API access before it can run.",
        notes="BLOCKED: create a GitHub issue and preserve the package; do not fake publish.",
    ),
}


def get_capability(platform_id: str) -> dict:
    cap = _CAPS.get(platform_id.lower())
    if not cap:
        return PlatformCapability(platform=platform_id, display_name=platform_id, publish=BLOCKED).to_dict()
    return cap.to_dict()


def publish_status(platform_id: str) -> str:
    cap = _CAPS.get(platform_id.lower())
    if cap is None:
        cap = PlatformCapability(platform=platform_id, display_name=platform_id)
    return cap.publish_status


def all_capabilities() -> dict:
    return {p: c.to_dict() for p, c in _CAPS.items()}


def assert_publishable(platform_id: str, allow_manual: bool = True) -> None:
    """Raise if a platform cannot be published to from this codebase.

    allow_manual=False also rejects MANUAL_REQUIRED (strict automation gate).
    """
    status = publish_status(platform_id)
    if status == BLOCKED:
        raise RuntimeError(
            f"Platform '{platform_id}' is BLOCKED: no implementation exists. "
            f"Create a GitHub issue and preserve the package; do not fake publish."
        )
    if not allow_manual and status == MANUAL_REQUIRED:
        raise RuntimeError(
            f"Platform '{platform_id}' requires MANUAL intervention; "
            f"automation gate (allow_manual=False) forbids auto-publish."
        )
