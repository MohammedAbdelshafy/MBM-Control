"""
Clip model — a generated video clip from a campaign's source content.
Status: generating → editing → qc_pending → qc_pass | qc_fail → approved | rejected → submitted
"""
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import TimestampMixin, UUIDPrimaryKey

if TYPE_CHECKING:
    from app.models.campaign import Campaign
    from app.models.deliverable import Deliverable
    from app.models.source_content import SourceContent


class ClipStatus:
    GENERATING = "generating"
    EDITING = "editing"
    QC_PENDING = "qc_pending"
    QC_PASS = "qc_pass"
    QC_FAIL = "qc_fail"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED_HUMAN = "rejected_human"
    SUBMITTED = "submitted"
    ACCEPTED = "accepted"
    REJECTED_PLATFORM = "rejected_platform"


class Clip(Base, UUIDPrimaryKey, TimestampMixin):
    __tablename__ = "clips"

    campaign_id: Mapped[str] = mapped_column(ForeignKey("campaigns.id"), nullable=False)
    source_content_id: Mapped[str] = mapped_column(
        ForeignKey("source_contents.id"), nullable=False
    )

    # Source window
    source_start_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    source_end_seconds: Mapped[float] = mapped_column(Float, nullable=False)

    # Output file
    storage_bucket: Mapped[str | None] = mapped_column(String(255), nullable=True)
    storage_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Video properties
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fps: Mapped[float | None] = mapped_column(Float, nullable=True)
    file_size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Generated content
    hook_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    captions_srt: Mapped[str | None] = mapped_column(Text, nullable=True)
    caption_style: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Scoring (0.0 - 1.0)
    overall_score: Mapped[float] = mapped_column(Float, default=0.0)
    scores: Mapped[dict] = mapped_column(JSON, default=dict)
    # {
    #   "requirements_match": 0.9, "duration_ok": 1.0,
    #   "resolution_ok": 1.0, "audio_quality": 0.85,
    #   "engagement_potential": 0.78, "hook_quality": 0.82
    # }

    # Editing metadata
    edit_template: Mapped[str | None] = mapped_column(String(255), nullable=True)
    edits_applied: Mapped[list] = mapped_column(JSON, default=list)
    # ["captions", "zoom", "silence_removal", "aspect_ratio_crop"]

    # Viral Benchmark & Enhancement Analysis
    viral_benchmark: Mapped[dict] = mapped_column(JSON, default=dict)
    enhanced_tags: Mapped[list] = mapped_column(JSON, default=list)
    platform_metadata: Mapped[dict] = mapped_column(JSON, default=dict)

    # Status
    status: Mapped[str] = mapped_column(String(50), default=ClipStatus.GENERATING)
    qc_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Human review
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Version tracking (re-processing creates new version)
    version: Mapped[int] = mapped_column(Integer, default=1)
    parent_clip_id: Mapped[str | None] = mapped_column(
        ForeignKey("clips.id"), nullable=True
    )

    campaign: Mapped["Campaign"] = relationship(back_populates="clips")
    source_content: Mapped["SourceContent"] = relationship(back_populates="clips")
    deliverable: Mapped["Deliverable | None"] = relationship(
        back_populates="clip", uselist=False
    )

    def __repr__(self) -> str:
        return f"<Clip id={self.id} score={self.overall_score:.2f} status={self.status}>"
