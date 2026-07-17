"""
EnhancementAgent — applies video quality enhancement to clips.
Runs FFmpeg filter pipeline (sharpen, color grade, denoise, re-encode)
and optionally ML upscaling via Real-ESRGAN. Can run standalone on
already-edited clips or be called as part of the editing pipeline.
"""
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.agents.base_agent import AgentResult, BaseAgent


class EnhancementAgent(BaseAgent):
    name = "enhancement_agent"

    def run(self, clip_id: str) -> AgentResult:
        from app.models.clip import Clip, ClipStatus
        from app.core.storage import download_file, upload_file
        from app.services.video_processor import VideoProcessor

        clip = self.db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            return AgentResult.fail(f"Clip {clip_id} not found")

        campaign = clip.campaign
        requirements = campaign.requirements if campaign else {}
        enhance_req = requirements.get("enhancement", {})
        upscale_req = requirements.get("upscale", {})
        enhancement_active = self.settings.enhancement_enabled or enhance_req.get("enabled", False)

        if not enhancement_active:
            return AgentResult.ok({"clip_id": clip_id, "message": "Enhancement not enabled (set ENHANCEMENT_ENABLED=true or campaign requirements.enhancement.enabled=true)"})

        self.logger.info(f"Enhancing clip {clip_id}")
        clip.status = ClipStatus.EDITING
        self.db.flush()

        with tempfile.TemporaryDirectory(prefix="clip_enhance_") as tmpdir:
            local_path = download_file(
                clip.storage_bucket,
                clip.storage_key,
                Path(tmpdir) / "input.mp4",
            )

            current = local_path
            enhancements = []

            # Step 1: FFmpeg filter enhancement
            enhanced = Path(tmpdir) / "enhanced.mp4"
            if VideoProcessor.enhance_video(
                current, enhanced,
                sharpen=enhance_req.get("sharpen", self.settings.enhancement_sharpen),
                sharpen_luma_strength=enhance_req.get("sharpen_luma_strength", self.settings.enhancement_sharpen_luma_strength),
                sharpen_luma_radius=enhance_req.get("sharpen_luma_radius", self.settings.enhancement_sharpen_luma_radius),
                sharpen_luma_threshold=enhance_req.get("sharpen_luma_threshold", self.settings.enhancement_sharpen_luma_threshold),
                sharpen_chroma_strength=enhance_req.get("sharpen_chroma_strength", self.settings.enhancement_sharpen_chroma_strength),
                sharpen_chroma_radius=enhance_req.get("sharpen_chroma_radius", self.settings.enhancement_sharpen_chroma_radius),
                sharpen_chroma_threshold=enhance_req.get("sharpen_chroma_threshold", self.settings.enhancement_sharpen_chroma_threshold),
                color_grade=enhance_req.get("color_grade", self.settings.enhancement_color_grade),
                contrast=enhance_req.get("contrast", self.settings.enhancement_contrast),
                brightness=enhance_req.get("brightness", self.settings.enhancement_brightness),
                saturation=enhance_req.get("saturation", self.settings.enhancement_saturation),
                denoise=enhance_req.get("denoise", self.settings.enhancement_denoise),
                denoise_spatial_luma=enhance_req.get("denoise_spatial_luma", self.settings.enhancement_denoise_spatial_luma),
                denoise_spatial_chroma=enhance_req.get("denoise_spatial_chroma", self.settings.enhancement_denoise_spatial_chroma),
                denoise_temp_luma=enhance_req.get("denoise_temp_luma", self.settings.enhancement_denoise_temp_luma),
                denoise_temp_chroma=enhance_req.get("denoise_temp_chroma", self.settings.enhancement_denoise_temp_chroma),
                crf=enhance_req.get("crf", self.settings.enhancement_crf),
                preset=enhance_req.get("preset", self.settings.enhancement_preset),
                fade_in=enhance_req.get("fade_in", 0),
                fade_out=enhance_req.get("fade_out", 0),
            ):
                current = enhanced
                enhancements.append("sharpen_color_denoise")

            # Step 2: Upscale (optional)
            upscale_active = self.settings.enhancement_upscale or upscale_req.get("enabled", False)
            if upscale_active:
                upscaled = Path(tmpdir) / "upscaled.mp4"
                model = upscale_req.get("model", "realesrgan-x4plus")
                scale = upscale_req.get("scale", 2)
                if VideoProcessor.real_esrgan_upscale(
                    current, upscaled,
                    model=model, scale=scale,
                    crf=enhance_req.get("crf", 18),
                    preset=enhance_req.get("preset", "slow"),
                    real_esrgan_bin=self.settings.real_esrgan_path,
                ):
                    current = upscaled
                    enhancements.append(f"upscaled_{scale}x_{model}")

            if not enhancements:
                return AgentResult.ok({"clip_id": clip_id, "message": "No enhancements applied"})

            # Upload enhanced clip
            enhanced_key = clip.storage_key.replace("/edited/", "/enhanced/")
            if enhanced_key == clip.storage_key:
                enhanced_key = clip.storage_key.replace(".mp4", "_enhanced.mp4")

            upload_file(
                current,
                self.settings.storage_bucket_clips,
                enhanced_key,
                content_type="video/mp4",
                metadata={"campaign_id": clip.campaign_id, "type": "enhanced"},
            )

            meta = self._probe_video(current)
            clip.storage_key = enhanced_key
            clip.duration_seconds = meta.get("duration", clip.duration_seconds)
            clip.width = meta.get("width")
            clip.height = meta.get("height")
            clip.fps = meta.get("fps")
            clip.file_size_bytes = current.stat().st_size
            if clip.edits_applied:
                clip.edits_applied = list(clip.edits_applied) + enhancements
            else:
                clip.edits_applied = enhancements
            clip.status = ClipStatus.QC_PENDING
            self.db.flush()

        self._audit("clip", clip.id, "enhanced", metadata={"enhancements": enhancements})

        # Telegram: notify + send enhanced clip
        try:
            from app.services.telegram_notifier import TelegramNotifier
            tg = TelegramNotifier(self.settings)
            tg.notify_enhancement_complete(clip, enhancements)
        except Exception as exc:
            self.logger.debug(f"Telegram enhancement notification skipped: {exc}")

        from app.workers.video_tasks import quality_check_clip
        quality_check_clip.apply_async(args=[clip_id], queue="video")

        return AgentResult.ok({"clip_id": clip_id, "enhancements": enhancements})

    def _probe_video(self, path: Path) -> dict:
        import json
        import subprocess
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_streams", "-show_format", str(path)],
                capture_output=True, text=True, timeout=30,
            )
            data = json.loads(result.stdout)
            fmt = data.get("format", {})
            video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
            fps_str = video.get("r_frame_rate", "30/1")
            n, d = fps_str.split("/") if "/" in fps_str else (fps_str, "1")
            return {
                "duration": float(fmt.get("duration", 0)),
                "width": video.get("width"),
                "height": video.get("height"),
                "fps": float(n) / float(d) if float(d) else 30.0,
            }
        except Exception:
            return {}
