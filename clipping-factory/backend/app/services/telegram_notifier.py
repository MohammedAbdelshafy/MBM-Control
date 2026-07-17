"""
TelegramNotifier — centralized Telegram notifications for the clipping pipeline.
Every agent uses this instead of raw HTTP calls. Supports:
- Text alerts with rich formatting
- Video clip sending (actual MP4 files)
- Thumbnail/preview generation
- Pipeline stage notifications (edit, QC, enhance, deliver, publish)
"""
import io
import json
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Optional

import httpx

from app.core.config import Settings, get_settings
from app.core.logging_config import get_logger
from app.core.storage import download_file, get_presigned_url

logger = get_logger("services.telegram")


class TelegramNotifier:
    def __init__(self, settings: Optional[Settings] = None):
        self.settings = settings or get_settings()
        self.bot_token = self.settings.telegram_bot_token
        self.chat_id = self.settings.telegram_chat_id
        self._api_base = f"https://api.telegram.org/bot{self.bot_token}"

    @property
    def enabled(self) -> bool:
        return bool(self.bot_token and self.chat_id)

    @property
    def _level(self) -> str:
        return (self.settings.telegram_notification_level or "important").lower()

    def _should_notify(self, category: str) -> bool:
        """Check if this notification category should be sent based on level.
        Categories: error, delivery, earnings, status (per-clip progress)
        """
        if self._level == "all":
            return True
        if self._level == "error":
            return category == "error"
        # important: delivery + earnings + errors + campaign summary
        return category in ("error", "delivery", "earnings", "summary")

    # ------------------------------------------------------------------
    # Low-level API calls
    # ------------------------------------------------------------------

    def _post(self, method: str, data: dict, files: Optional[dict] = None) -> Optional[dict]:
        if not self.enabled:
            return None
        url = f"{self._api_base}/{method}"
        try:
            with httpx.Client(timeout=30) as client:
                if files:
                    resp = client.post(url, data=data, files=files)
                else:
                    resp = client.post(url, json=data)
                if resp.status_code == 200:
                    return resp.json()
                logger.warning(f"Telegram {method} {resp.status_code}: {resp.text[:200]}")
                return None
        except Exception as exc:
            logger.error(f"Telegram {method} failed: {exc}")
            return None

    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        return self._post("sendMessage", {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": parse_mode,
            "disable_web_page_preview": False,
        }) is not None

    def send_video(self, video_path: Path, caption: str = "", thumbnail_path: Optional[Path] = None) -> bool:
        if not video_path.exists():
            logger.warning(f"Video not found: {video_path}")
            return False
        files = {"video": (video_path.name, video_path.read_bytes(), "video/mp4")}
        data = {
            "chat_id": self.chat_id,
            "caption": caption,
            "parse_mode": "Markdown",
            "supports_streaming": True,
        }
        if thumbnail_path and thumbnail_path.exists():
            files["thumbnail"] = (thumbnail_path.name, thumbnail_path.read_bytes(), "image/jpeg")
            data["thumb"] = "attach://thumbnail"
        return self._post("sendVideo", data, files) is not None

    def send_photo(self, photo_path: Path, caption: str = "") -> bool:
        if not photo_path.exists():
            return False
        files = {"photo": (photo_path.name, photo_path.read_bytes(), "image/jpeg")}
        return self._post("sendPhoto", {"chat_id": self.chat_id, "caption": caption, "parse_mode": "Markdown"}, files) is not None

    def send_document(self, doc_path: Path, caption: str = "") -> bool:
        if not doc_path.exists():
            return False
        files = {"document": (doc_path.name, doc_path.read_bytes(), "application/octet-stream")}
        return self._post("sendDocument", {"chat_id": self.chat_id, "caption": caption, "parse_mode": "Markdown"}, files) is not None

    # ------------------------------------------------------------------
    # Thumbnail generation
    # ------------------------------------------------------------------

    def _generate_thumbnail(self, video_path: Path) -> Optional[Path]:
        """Extract a frame at 25% duration as a JPEG thumbnail."""
        thumb = video_path.parent / f"{video_path.stem}_thumb.jpg"
        try:
            duration = self._get_duration(video_path)
            timestamp = max(1.0, duration * 0.25)
            subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_streams", "-show_format", str(video_path)],
                capture_output=True, text=True, timeout=15,
            )
            subprocess.run(
                [self.settings.ffmpeg_path or "ffmpeg", "-y",
                 "-ss", str(timestamp),
                 "-i", str(video_path),
                 "-vframes", "1",
                 "-q:v", "2",
                 "-vf", "scale=320:-1",
                 str(thumb)],
                capture_output=True, text=True, timeout=30,
            )
            return thumb if thumb.exists() else None
        except Exception as exc:
            logger.debug(f"Thumbnail failed: {exc}")
            return None

    def _get_duration(self, path: Path) -> float:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_format", str(path)],
                capture_output=True, text=True, timeout=15,
            )
            data = json.loads(result.stdout)
            return float(data.get("format", {}).get("duration", 0))
        except Exception:
            return 0.0

    def _format_size(self, bytes_val: int) -> str:
        if bytes_val < 1024 * 1024:
            return f"{bytes_val / 1024:.0f} KB"
        return f"{bytes_val / 1024 / 1024:.1f} MB"

    # ------------------------------------------------------------------
    # Rich notifications — sent by agents
    # ------------------------------------------------------------------

    def notify_clip_generated(self, clip) -> bool:
        """Clip generated from source content."""
        if not self._should_notify("status"):
            return False
        campaign = clip.campaign
        title = campaign.title if campaign else "Unknown"
        brand = campaign.brand_name if campaign and campaign.brand_name else ""
        dur = clip.source_end_seconds - clip.source_start_seconds
        text = (
            f"🎬 *Clip Generated*\n"
            f"Campaign: {title}\n"
            f"Brand: {brand or '—'}\n"
            f"Duration: {dur:.0f}s\n"
            f"ID: `{clip.id[:12]}...`"
        )
        return self.send_message(text)

    def notify_edit_complete(self, clip) -> bool:
        """Editing pipeline finished — send clip preview + edit summary."""
        if not self._should_notify("status"):
            return False
        campaign = clip.campaign
        title = campaign.title if campaign else "Unknown"
        brand = campaign.brand_name if campaign and campaign.brand_name else ""
        edits = clip.edits_applied or []
        dur = clip.duration_seconds or 0

        text = (
            f"✂️ *Clip Edited*\n"
            f"Campaign: {title}\n"
            f"Brand: {brand or '—'}\n"
            f"Duration: {dur:.0f}s\n"
            f"Edits: {', '.join(edits[:5])}{'…' if len(edits) > 5 else ''}\n"
            f"Resolution: {clip.width}×{clip.height} @ {clip.fps:.0f}fps\n"
            f"Size: {self._format_size(clip.file_size_bytes or 0)}"
        )

        # Try to send the actual clip
        if clip.storage_bucket and clip.storage_key:
            return self._send_clip_from_storage(clip.storage_bucket, clip.storage_key, text)
        return self.send_message(text)

    def notify_qc_result(self, clip) -> bool:
        """QC pass/fail with scores — send clip if pass."""
        if not self._should_notify("status"):
            return False
        campaign = clip.campaign
        title = campaign.title if campaign else "Unknown"
        passed = clip.status in ("qc_pass", "awaiting_approval", "approved")
        score = clip.overall_score or 0.0
        scores = clip.scores or {}
        score_lines = "\n".join(f"  • {k}: {v:.1f}" for k, v in scores.items() if isinstance(v, (int, float)))

        icon = "✅" if passed else "❌"
        text = (
            f"{icon} *QC {'Passed' if passed else 'Failed'}*\n"
            f"Campaign: {title}\n"
            f"Overall Score: {score:.2f}\n"
            f"{score_lines}\n"
            f"Notes: {clip.qc_notes or '—'}"
        )

        if passed and clip.storage_bucket and clip.storage_key:
            return self._send_clip_from_storage(clip.storage_bucket, clip.storage_key, text)
        return self.send_message(text)

    def notify_enhancement_complete(self, clip, enhancements: list[str]) -> bool:
        """Enhancement pipeline finished — send enhanced clip."""
        if not self._should_notify("status"):
            return False
        campaign = clip.campaign
        title = campaign.title if campaign else "Unknown"

        text = (
            f"✨ *Clip Enhanced*\n"
            f"Campaign: {title}\n"
            f"Enhancements: {', '.join(enhancements)}\n"
            f"Resolution: {clip.width}×{clip.height}\n"
            f"Size: {self._format_size(clip.file_size_bytes or 0)}"
        )

        if clip.storage_bucket and clip.storage_key:
            return self._send_clip_from_storage(clip.storage_bucket, clip.storage_key, text)
        return self.send_message(text)

    def notify_delivery_submitted(self, clip, deliverable, submission) -> bool:
        """Clip submitted to clipping.com — send clip + submission info."""
        if not self._should_notify("delivery"):
            return False
        campaign = clip.campaign
        title = campaign.title if campaign else "Unknown"
        brand = campaign.brand_name if campaign and campaign.brand_name else ""

        text = (
            f"📤 *Clip Submitted*\n"
            f"Campaign: {title}\n"
            f"Brand: {brand or '—'}\n"
            f"Duration: {clip.duration_seconds:.0f}s\n"
            f"Score: {clip.overall_score:.2f}\n"
            f"Submission: `{submission.id[:12]}...`"
        )

        bucket = getattr(deliverable, "storage_bucket", None) or clip.storage_bucket
        key = getattr(deliverable, "storage_key", None) or clip.storage_key
        if bucket and key:
            return self._send_clip_from_storage(bucket, key, text)
        return self.send_message(text)

    def notify_clip_published(self, platform: str, clip, post_url: str) -> bool:
        """Clip published to social platform — send clip + link."""
        if not self._should_notify("delivery"):
            return False
        campaign = clip.campaign
        title = campaign.title if campaign else "Unknown"
        brand = campaign.brand_name if campaign and campaign.brand_name else ""

        text = (
            f"🌐 *Clip Published*\n"
            f"Platform: {platform.title()}\n"
            f"Campaign: {brand or title}\n"
            f"URL: {post_url}\n"
            f"ID: `{clip.id[:12]}...`"
        )

        if clip.storage_bucket and clip.storage_key:
            return self._send_clip_from_storage(clip.storage_bucket, clip.storage_key, text)
        return self.send_message(text)

    def notify_clip_accepted(self, clip, payout: float) -> bool:
        """Clip accepted by platform — earnings update."""
        if not self._should_notify("earnings"):
            return False
        campaign = clip.campaign
        title = campaign.title if campaign else "Unknown"
        text = (
            f"💰 *Clip Accepted — Earned!*\n"
            f"Campaign: {title}\n"
            f"Payout: ${payout:.2f}\n"
            f"Duration: {clip.duration_seconds:.0f}s\n"
            f"Score: {clip.overall_score:.2f}\n"
            f"ID: `{clip.id[:12]}...`"
        )
        return self.send_message(text)

    def notify_error(self, stage: str, clip_id: str, error: str) -> bool:
        """Critical error alert."""
        if not self._should_notify("error"):
            return False
        text = (
            f"🚨 *Pipeline Error*\n"
            f"Stage: {stage}\n"
            f"Clip: `{clip_id[:12]}...`\n"
            f"Error: `{error[:200]}`"
        )
        return self.send_message(text)

    def notify_campaign_complete(self, campaign) -> bool:
        """All clips in campaign processed."""
        if not self._should_notify("summary"):
            return False
        title = campaign.title or "Unknown"
        brand = campaign.brand_name or ""
        clips_count = len(campaign.clips) if hasattr(campaign, "clips") else 0
        text = (
            f"🏁 *Campaign Complete*\n"
            f"Campaign: {title}\n"
            f"Brand: {brand}\n"
            f"Clips: {clips_count}\n"
            f"ID: `{campaign.id[:12]}...`"
        )
        return self.send_message(text)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _send_clip_from_storage(self, bucket: str, key: str, caption: str) -> bool:
        """Download clip from storage and send to Telegram with thumbnail."""
        try:
            with tempfile.TemporaryDirectory(prefix="tg_clip_") as tmpdir:
                local = Path(tmpdir) / "clip.mp4"
                download_file(bucket, key, local)
                if not local.exists() or local.stat().st_size == 0:
                    return self.send_message(caption + "\n\n*(video unavailable)*")
                thumb = self._generate_thumbnail(local)
                result = self.send_video(local, caption, thumb)
                if not result:
                    # Fallback: send as document
                    result = self.send_document(local, caption)
                return result
        except Exception as exc:
            logger.error(f"Failed to send clip from storage: {exc}")
            # Fallback: send link
            try:
                url = get_presigned_url(bucket, key)
                return self.send_message(caption + f"\n\n[Download Link]({url})")
            except Exception:
                return self.send_message(caption)
