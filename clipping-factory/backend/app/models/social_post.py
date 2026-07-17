"""
SocialPost model — tracks each publish attempt of a clip to any platform
(TikTok, Instagram, YouTube, Vyro, Reach.cat, ClipAffiliates) via browser
automation or API. Also tracks performance metrics (views, likes, earnings)
for analytics.

A single clip can be published to multiple platforms, so (clip_id, platform)
is the natural grain — unlike Submission, which is 1:1 with a Clipping.com
deliverable. Mirrors the audit/earnings shape of Submission for consistency.
"""
from typing import TYPE_CHECKING

from sqlalchemy import JSON, BigInteger, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.clip import Clip


class SocialPlatform:
    TIKTOK = "tiktok"
    INSTAGRAM = "instagram"
    YOUTUBE = "youtube"
    LINKEDIN = "linkedin"
    TWITTER = "twitter"

    # Clipping economy platforms (2026)
    VYRO = "vyro"                         # $3 CPM, MrBeast-backed
    REACH_CAT = "reach_cat"               # $1–$6 CPM, highest ceiling, no KYC
    CLIP_AFFILIATES = "clip_affiliates"   # $1–$5 CPM, brand marketplace
    CLIPPING_COM = "clipping_com"         # Up to $3 CPM, original platform

    ALL_PLATFORMS = (
        TIKTOK, INSTAGRAM, YOUTUBE, LINKEDIN, TWITTER,
        VYRO, REACH_CAT, CLIP_AFFILIATES, CLIPPING_COM,
    )

    # Known CPM rates for revenue projection
    CPM_RATES = {
        TIKTOK: 0.30,
        INSTAGRAM: 3.00,
        YOUTUBE: 1.50,
        LINKEDIN: 4.00,
        TWITTER: 0.50,
        VYRO: 3.00,
        REACH_CAT: 3.50,
        CLIP_AFFILIATES: 3.00,
        CLIPPING_COM: 2.00,
    }

    @classmethod
    def resolve(cls, platforms: list[str] | None) -> list[str]:
        """Resolve 'all' to all platforms; pass through specific platforms."""
        if not platforms:
            return []
        resolved = []
        for p in platforms:
            if p == "all":
                resolved.extend(cls.ALL_PLATFORMS)
            else:
                resolved.append(p.lower())
        return list(dict.fromkeys(resolved))  # deduplicate preserving order

    @classmethod
    def estimated_cpm(cls, platform: str) -> float:
        return cls.CPM_RATES.get(platform, 1.0)

    @classmethod
    def projected_earnings(cls, platform: str, views: int) -> float:
        """Estimate earnings for a given view count on a platform."""
        cpm = cls.estimated_cpm(platform)
        return (views / 1000) * cpm


class SocialPostStatus:
    PENDING = "pending"
    UPLOADING = "uploading"
    PUBLISHED = "published"
    FAILED = "failed"
    SIMULATED = "simulated"   # produced by the mock fallback (no creds / no Playwright)


class SocialPost(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "social_posts"

    clip_id: Mapped[str] = mapped_column(ForeignKey("clips.id"), nullable=False)
    campaign_id: Mapped[str | None] = mapped_column(
        ForeignKey("campaigns.id"), nullable=True
    )

    platform: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(50), default=SocialPostStatus.PENDING)

    # What we posted
    caption: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Platform response
    platform_post_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    post_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Attempt tracking
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    post_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    # Performance metrics (synced from platform analytics)
    views: Mapped[int] = mapped_column(BigInteger, default=0)
    likes: Mapped[int] = mapped_column(BigInteger, default=0)
    shares: Mapped[int] = mapped_column(BigInteger, default=0)
    comments: Mapped[int] = mapped_column(BigInteger, default=0)
    earnings_usd: Mapped[float] = mapped_column(Float, default=0.0)
    last_synced_at: Mapped[str | None] = mapped_column(String(50), nullable=True)

    clip: Mapped["Clip"] = relationship()

    def __repr__(self) -> str:
        return f"<SocialPost clip={self.clip_id[:8]} {self.platform} status={self.status}>"
