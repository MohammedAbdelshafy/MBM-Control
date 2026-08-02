"""
Campaign model — a discovered Clipping.com campaign with full requirements profile.
Status transitions: discovered → analyzing → ready → processing → delivering → done | failed
"""
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.clip import Clip
    from app.models.page import Page
    from app.models.source_content import SourceContent
    from app.models.job import Job


class CampaignStatus:
    DISCOVERED = "discovered"
    ANALYZING = "analyzing"
    READY = "ready"
    PROCESSING = "processing"
    QC = "qc"
    AWAITING_APPROVAL = "awaiting_approval"
    DELIVERING = "delivering"
    COMPLETED = "completed"
    FAILED = "failed"
    PAUSED = "paused"
    EXPIRED = "expired"


class Campaign(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "campaigns"

    # Platform identity
    platform_campaign_id: Mapped[str | None] = mapped_column(String(255), unique=True, nullable=True)
    page_id: Mapped[str | None] = mapped_column(ForeignKey("pages.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    brand_name: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), default=CampaignStatus.DISCOVERED)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=5)  # 1 (highest) to 10

    # Raw data from Clipping.com
    raw_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    campaign_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    docs_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # Google Doc / PDF brief

    # Parsed requirements (populated by Campaign Intelligence Agent)
    requirements: Mapped[dict] = mapped_column(JSON, default=dict)
    # Structure:
    # {
    #   "duration_min": 30, "duration_max": 60,
    #   "aspect_ratio": "9:16", "platform": "TikTok",
    #   "caption_required": true, "hook_required": true,
    #   "resolution": "1080x1920", "fps": 30,
    #   "style_notes": "...", "banned_words": [],
    #   "due_date": "2026-07-01", "max_submissions": 5,
    #   "payment_per_clip": 25.00, "currency": "USD"
    # }

    # Source material
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # youtube | gdrive | dropbox | direct | manual

    # Financials
    payment_per_accepted_clip: Mapped[float | None] = mapped_column(Float, nullable=True)
    payout_per_1k_views: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_payout_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    estimated_earnings: Mapped[float] = mapped_column(Float, default=0.0)
    actual_earnings: Mapped[float] = mapped_column(Float, default=0.0)
    platform_name: Mapped[str] = mapped_column(String(50), default="Clipping.com")

    # Processing results
    clips_generated: Mapped[int] = mapped_column(Integer, default=0)
    clips_submitted: Mapped[int] = mapped_column(Integer, default=0)
    clips_accepted: Mapped[int] = mapped_column(Integer, default=0)
    clips_rejected: Mapped[int] = mapped_column(Integer, default=0)

    # Due date
    due_at: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Error tracking
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)

    # Agent notes
    intelligence_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    opportunity_score: Mapped[float] = mapped_column(Float, default=0.0)

    # Relationships
    page: Mapped["Page"] = relationship(back_populates="campaigns")
    source_contents: Mapped[list["SourceContent"]] = relationship(back_populates="campaign")
    clips: Mapped[list["Clip"]] = relationship(back_populates="campaign")
    jobs: Mapped[list["Job"]] = relationship(back_populates="campaign")

    def __repr__(self) -> str:
        return f"<Campaign id={self.id} title={self.title[:40]} status={self.status}>"
