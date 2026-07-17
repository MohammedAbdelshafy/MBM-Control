"""
EditingAgent — applies all post-processing edits to a raw clip.

Edits applied (all configurable per campaign requirements):
- Aspect ratio conversion (crop/pad to 9:16, 9:16, 1:1)
- Auto-captions (SRT burned-in via ffmpeg + optional sidecar .srt)
- Hook text overlay
- Silence removal
- Zoom effects (Ken Burns)
- Audio normalization
- Background music (optional)
- Resolution normalization
- Voice-over / TTS narration (via edge-tts)
- Watermark / logo overlay
- Multi-segment assembly with transitions
- B-roll image overlay

- Enhancement (sharpen, color grade, denoise)
- Upscale (Real-ESRGAN or lanczos fallback)

All edits use FFmpeg; edge-tts for voiceover.
"""
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base_agent import AgentResult, BaseAgent


# Aspect ratio configs
ASPECT_RATIO_MAP = {
    "9:16": {"width": 1080, "height": 1920},
    "16:9": {"width": 1920, "height": 1080},
    "1:1": {"width": 1080, "height": 1080},
    "4:5": {"width": 1080, "height": 1350},
}


class EditingAgent(BaseAgent):
    name = "editing_agent"

    def run(self, clip_id: str) -> AgentResult:
        from app.models.clip import Clip, ClipStatus
        from app.core.storage import download_file, upload_file

        clip = self.db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            return AgentResult.fail(f"Clip {clip_id} not found")

        campaign = clip.campaign
        requirements = campaign.requirements if campaign else {}

        self.logger.info(f"Editing clip {clip_id}")
        clip.status = ClipStatus.EDITING
        self.db.flush()

        with tempfile.TemporaryDirectory(prefix="clip_edit_") as tmpdir:
            # Download raw clip
            raw_path = download_file(
                clip.storage_bucket,
                clip.storage_key,
                Path(tmpdir) / "raw.mp4",
            )

            # Build edit pipeline
            edited_path, edits_applied = self._apply_edits(
                raw_path=raw_path,
                requirements=requirements,
                clip=clip,
                transcript=clip.source_content.transcript if clip.source_content else None,
                tmpdir=tmpdir,
            )

            if not edited_path or not edited_path.exists():
                clip.status = ClipStatus.QC_FAIL
                clip.qc_notes = "Editing pipeline failed to produce output"
                self.db.flush()
                return AgentResult.fail("Editing failed")

            # Generate hook text variants for A/B testing
            hooks = self._generate_hook_variants(
                clip=clip,
                requirements=requirements,
                transcript_window=self._get_transcript_window(clip),
            )
            clip.hook_text = hooks[0] if hooks else None
            clip.scores["hook_variants"] = hooks
            if len(hooks) > 1:
                edits_applied.append(f"ab_hooks_{len(hooks)}_variants")

            # Generate voice-over / TTS if configured
            if requirements.get("voiceover_required", False):
                voiceover_path = self._generate_voiceover(
                    clip=clip,
                    requirements=requirements,
                    tmpdir=tmpdir,
                )
                if voiceover_path and voiceover_path.exists():
                    mixed_path = Path(tmpdir) / "with_voiceover.mp4"
                    from app.services.video_processor import VideoProcessor
                    if VideoProcessor.mix_voiceover(edited_path, voiceover_path, mixed_path):
                        edited_path = mixed_path
                        edits_applied.append("voiceover_added")

            # Generate background music if configured
            bgm = requirements.get("background_music")
            if bgm:
                bgm_path = Path(tmpdir) / "bgm.mp3"
                try:
                    from app.core.storage import download_file as dl
                    dl(self.settings.storage_bucket_clips, bgm, bgm_path)
                    from app.services.video_processor import VideoProcessor
                    bgm_out = Path(tmpdir) / "with_bgm.mp4"
                    volume = requirements.get("background_music_volume", 0.1)
                    if VideoProcessor.add_background_music(edited_path, bgm_path, bgm_out, volume):
                        edited_path = bgm_out
                        edits_applied.append("background_music_added")
                except Exception as exc:
                    self.logger.warning(f"Background music skipped: {exc}")

            # Add watermark / logo if configured
            watermark_path_config = requirements.get("watermark_path")
            if watermark_path_config:
                try:
                    watermark_file = Path(tmpdir) / "watermark.png"
                    from app.core.storage import download_file as dl
                    dl(self.settings.storage_bucket_clips, watermark_path_config, watermark_file)
                    if watermark_file.exists():
                        wm_out = Path(tmpdir) / "watermarked.mp4"
                        from app.services.video_processor import VideoProcessor
                        wm_pos = requirements.get("watermark_position", "bottom_right")
                        if VideoProcessor.add_watermark(edited_path, watermark_file, wm_out, wm_pos):
                            edited_path = wm_out
                            edits_applied.append("watermark_added")
                except Exception as exc:
                    self.logger.warning(f"Watermark skipped: {exc}")

            # Generate SRT captions
            srt = self._generate_captions_srt(clip)
            clip.captions_srt = srt

            # Also write sidecar SRT if configured
            if requirements.get("sidecar_captions", False) and srt:
                srt_sidecar_path = Path(tmpdir) / "captions.srt"
                srt_sidecar_path.write_text(srt, encoding="utf-8")
                from app.core.storage import upload_file as uf
                sidecar_key = clip.storage_key.replace("/raw/", "/edited/").replace(".mp4", ".srt")
                uf(
                    srt_sidecar_path,
                    self.settings.storage_bucket_clips,
                    sidecar_key,
                    content_type="text/plain",
                    metadata={"campaign_id": clip.campaign_id, "type": "captions"},
                )
                edits_applied.append("sidecar_srt_generated")

            # Burn captions if required
            if requirements.get("caption_required", True) and srt:
                srt_path = Path(tmpdir) / "captions_burn.srt"
                srt_path.write_text(srt, encoding="utf-8")
                captioned_path = Path(tmpdir) / "captioned.mp4"
                self._burn_captions(edited_path, srt_path, captioned_path, requirements)
                if captioned_path.exists():
                    edited_path = captioned_path
                    edits_applied.append("captions_burned")

            # Upload edited clip
            edited_key = clip.storage_key.replace("/raw/", "/edited/")
            upload_file(
                edited_path,
                self.settings.storage_bucket_clips,
                edited_key,
                content_type="video/mp4",
                metadata={"campaign_id": clip.campaign_id, "type": "edited"},
            )

            # Update clip record
            meta = self._probe_video(edited_path)
            clip.storage_key = edited_key
            clip.duration_seconds = meta.get("duration", clip.duration_seconds)
            clip.width = meta.get("width")
            clip.height = meta.get("height")
            clip.fps = meta.get("fps")
            clip.file_size_bytes = edited_path.stat().st_size
            clip.edits_applied = edits_applied
            clip.edit_template = requirements.get("aspect_ratio", "9:16")
            clip.status = ClipStatus.QC_PENDING
            self.db.flush()

        self._audit("clip", clip.id, "edited", metadata={"edits": edits_applied})

        # Telegram: notify + send clip preview
        try:
            from app.services.telegram_notifier import TelegramNotifier
            tg = TelegramNotifier(self.settings)
            tg.notify_edit_complete(clip)
        except Exception as exc:
            self.logger.debug(f"Telegram edit notification skipped: {exc}")

        # Trigger Editor QA (professional quality gate)
        from app.workers.video_tasks import editor_quality_check
        editor_quality_check.apply_async(args=[clip_id, True], queue="video")

        return AgentResult.ok({"clip_id": clip_id, "edits": edits_applied})

    # ------------------------------------------------------------------
    # Edit pipeline
    # ------------------------------------------------------------------

    def _apply_edits(
        self, raw_path: Path, requirements: dict, clip, transcript, tmpdir: str
    ) -> tuple[Path | None, list[str]]:
        edits = []
        current = raw_path

        # 0. Multi-segment assembly with transitions (if configured)
        segments = requirements.get("segments", [])
        if segments and len(segments) > 1:
            from app.services.video_processor import VideoProcessor
            transition = requirements.get("transition", "fade")
            trans_duration = requirements.get("transition_duration", 0.5)
            segment_paths = []
            for i, seg_info in enumerate(segments):
                seg_path = Path(tmpdir) / f"segment_{i}.mp4"
                start = seg_info.get("start", 0)
                end = seg_info.get("end", 30)
                dur = end - start
                cmd = [
                    self.settings.ffmpeg_path, "-y",
                    "-ss", str(start),
                    "-i", str(current),
                    "-t", str(dur),
                    "-c", "copy",
                    str(seg_path),
                ]
                if self._run_ffmpeg(cmd) and seg_path.exists():
                    segment_paths.append(seg_path)

            if len(segment_paths) > 1:
                stitched = Path(tmpdir) / "stitched.mp4"
                if VideoProcessor.crossfade_clips(segment_paths, stitched, tmpdir, transition, trans_duration):
                    current = stitched
                    edits.append(f"multi_segment_{len(segment_paths)}_parts")
            elif segment_paths:
                current = segment_paths[0]

        # 1. Speed ramping (if configured)
        speed = requirements.get("speed_ramp")
        if speed:
            out = Path(tmpdir) / "speed_ramped.mp4"
            if self._apply_speed_ramp(current, out, speed):
                current = out
                edits.append(f"speed_ramp_{speed}x")

        # 2. Ken Burns / zoom effect (if configured)
        zoom = requirements.get("ken_burns")
        if zoom:
            out = Path(tmpdir) / "ken_burns.mp4"
            if self._apply_ken_burns(current, out, zoom):
                current = out
                edits.append(f"ken_burns_{zoom.get('style', 'slow_zoom_in')}")

        # 3. Aspect ratio conversion
        aspect = requirements.get("aspect_ratio", "9:16")
        if aspect in ASPECT_RATIO_MAP:
            target = ASPECT_RATIO_MAP[aspect]
            out = Path(tmpdir) / "ar_converted.mp4"
            if self._convert_aspect_ratio(current, out, target["width"], target["height"]):
                current = out
                edits.append(f"aspect_ratio_{aspect.replace(':', 'x')}")

        # 4. Audio normalization
        out = Path(tmpdir) / "normalized.mp4"
        if self._normalize_audio(current, out):
            current = out
            edits.append("audio_normalized")

        # 5. Silence removal (configurable threshold)
        if requirements.get("remove_silence", False):
            out = Path(tmpdir) / "no_silence.mp4"
            if self._remove_silence(current, out):
                current = out
                edits.append("silence_removed")

        # 6. Resolution normalization
        res = requirements.get("resolution")
        if res:
            parts = res.lower().replace("x", "x").split("x")
            if len(parts) == 2:
                w, h = int(parts[0]), int(parts[1])
                out = Path(tmpdir) / "resized.mp4"
                if self._resize(current, out, w, h):
                    current = out
                    edits.append(f"resized_{w}x{h}")

        # 7. B-roll image overlay
        broll = requirements.get("broll_image_path")
        if broll:
            broll_path = Path(tmpdir) / "broll.png"
            try:
                from app.core.storage import download_file as dl
                dl(self.settings.storage_bucket_clips, broll, broll_path)
                if broll_path.exists():
                    broll_out = Path(tmpdir) / "with_broll.mp4"
                    from app.services.video_processor import VideoProcessor
                    broll_pos = requirements.get("broll_position", "center")
                    broll_scale = requirements.get("broll_scale")
                    if VideoProcessor.add_image_overlay(current, broll_path, broll_out, broll_pos, broll_scale):
                        current = broll_out
                        edits.append("broll_overlay_added")
            except Exception as exc:
                self.logger.warning(f"B-roll overlay skipped: {exc}")

        # 8. Fade in/out
        fade_in = requirements.get("fade_in", 0)
        fade_out = requirements.get("fade_out", 0)
        if fade_in > 0 or fade_out > 0:
            from app.services.video_processor import VideoProcessor
            faded = Path(tmpdir) / "faded.mp4"
            if VideoProcessor.add_fade(current, faded, fade_in, fade_out):
                current = faded
                edits.append(f"fade_in_{fade_in}s_fade_out_{fade_out}s")

        # 9. Enhancement (sharpen, color grade, denoise)
        enhance_req = requirements.get("enhancement", {})
        enhancement_active = self.settings.enhancement_enabled or enhance_req.get("enabled", False)
        if enhancement_active:
            from app.services.video_processor import VideoProcessor
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
                fade_in=0,
                fade_out=0,
            ):
                current = enhanced
                edits.append("enhanced_sharpen_color_denoise")

        # 10. Upscale (Real-ESRGAN or fallback lanczos)
        #     Skip when an explicit target resolution is set and upscaling
        #     would overshoot it (QC requires the exact target dimensions).
        upscale_req = requirements.get("upscale", {})
        upscale_active = self.settings.enhancement_upscale or upscale_req.get("enabled", False)
        if upscale_active:
            from app.services.video_processor import VideoProcessor
            upscaled = Path(tmpdir) / "upscaled.mp4"
            model = upscale_req.get("model", "realesrgan-x4plus")
            scale = upscale_req.get("scale", 2)
            _overshoot = False
            if res:
                try:
                    from app.services.video_processor import VideoProcessor as _VP
                    _w, _h = _VP.get_video_dimensions(str(current))
                    if _w and _h and (_w * scale > w or _h * scale > h):
                        _overshoot = True
                        self.logger.info(
                            f"Upscale skipped: {_w}x{_h} *{scale} would exceed "
                            f"target {w}x{h}"
                        )
                except Exception:
                    pass
            if not _overshoot and VideoProcessor.real_esrgan_upscale(
                current, upscaled,
                model=model, scale=scale,
                crf=enhance_req.get("crf", 18) if enhance_req.get("enabled", False) else 18,
                preset=enhance_req.get("preset", "slow") if enhance_req.get("enabled", False) else "slow",
                real_esrgan_bin=self.settings.real_esrgan_path,
            ):
                current = upscaled
                edits.append(f"upscaled_{scale}x_{model}")

        return current, edits

    def _convert_aspect_ratio(self, src: Path, dst: Path, width: int, height: int) -> bool:
        """Crop and scale to target dimensions maintaining center framing."""
        cmd = [
            self.settings.ffmpeg_path, "-y",
            "-i", str(src),
            "-vf", (
                f"scale={width}:{height}:flags=lanczos:force_original_aspect_ratio=increase,"
                f"crop={width}:{height}"
            ),
            "-c:v", "libx264", "-crf", "16", "-preset", "veryslow",
            "-tune", "film",
            "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
            str(dst),
        ]
        return self._run_ffmpeg(cmd)

    def _normalize_audio(self, src: Path, dst: Path) -> bool:
        """Two-pass loudnorm audio normalization to -14 LUFS (broadcast standard)."""
        # Pass 1: measure
        cmd_measure = [
            self.settings.ffmpeg_path, "-y",
            "-i", str(src),
            "-af", "loudnorm=I=-14:TP=-1.5:LRA=11:print_format=json",
            "-f", "null", "-",
        ]
        import json as _json
        try:
            result = subprocess.run(cmd_measure, capture_output=True, text=True, timeout=60)
            stderr = result.stderr or ""
            import re
            match = re.search(r'\{[^}]*"input_i"[^}]*\}', stderr, re.DOTALL)
            if match:
                stats = _json.loads(match.group())
                # Pass 2: apply measured values
                cmd = [
                    self.settings.ffmpeg_path, "-y",
                    "-i", str(src),
                    "-af", (
                        f"loudnorm=I=-14:TP=-1.5:LRA=11"
                        f":measured_I={stats.get('input_i', '-14')}"
                        f":measured_TP={stats.get('input_tp', '-2')}"
                        f":measured_LRA={stats.get('input_lra', '7')}"
                        f":measured_thresh={stats.get('input_thresh', '-24')}"
                        f":linear=true"
                    ),
                    "-c:v", "copy",
                    str(dst),
                ]
                return self._run_ffmpeg(cmd)
        except Exception:
            pass
        # Fallback: single pass
        cmd = [
            self.settings.ffmpeg_path, "-y",
            "-i", str(src),
            "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
            "-c:v", "copy",
            str(dst),
        ]
        return self._run_ffmpeg(cmd)

    def _remove_silence(self, src: Path, dst: Path, threshold_db: float = -35.0) -> bool:
        """Remove silent sections below threshold."""
        cmd = [
            self.settings.ffmpeg_path, "-y",
            "-i", str(src),
            "-af", f"silenceremove=start_periods=1:start_silence=0.3:start_threshold={threshold_db}dB",
            "-c:v", "copy",
            str(dst),
        ]
        return self._run_ffmpeg(cmd)

    def _resize(self, src: Path, dst: Path, width: int, height: int) -> bool:
        cmd = [
            self.settings.ffmpeg_path, "-y",
            "-i", str(src),
            "-vf", f"scale={width}:{height}:flags=lanczos",
            "-c:v", "libx264", "-crf", "16", "-preset", "veryslow",
            "-tune", "film",
            "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
            str(dst),
        ]
        return self._run_ffmpeg(cmd)

    def _apply_speed_ramp(self, src: Path, dst: Path, speed: float) -> bool:
        """Apply speed ramping effect. speed > 1.0 = fast forward, < 1.0 = slow motion."""
        atempo = 1.0 / speed
        cmd = [
            self.settings.ffmpeg_path, "-y",
            "-i", str(src),
            "-vf", f"setpts={1.0/speed}*PTS",
            "-af", f"atempo={max(0.5, min(100.0, atempo))}",
            "-c:v", "libx264", "-crf", "16", "-preset", "veryslow",
            "-tune", "film",
            "-c:a", "aac", "-b:a", "320k",
            str(dst),
        ]
        return self._run_ffmpeg(cmd)

    def _apply_ken_burns(self, src: Path, dst: Path, config: dict) -> bool:
        """
        Apply Ken Burns zoom/pan effect.
        config examples:
          {"style": "slow_zoom_in", "zoom": 0.02}
          {"style": "slow_zoom_out", "zoom": -0.02}
          {"style": "pan_right", "pan_x": 0.3}
          {"style": "pan_up", "pan_y": 0.2}
        """
        style = config.get("style", "slow_zoom_in")
        zoom = config.get("zoom", 0.015)
        pan_x = config.get("pan_x", 0)
        pan_y = config.get("pan_y", 0)

        # Use zoompan filter for Ken Burns effect
        if style == "slow_zoom_in":
            vf = f"zoompan=z='min(zoom+{zoom},1.5)':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080"
        elif style == "slow_zoom_out":
            vf = f"zoompan=z='max(zoom-{abs(zoom)},1.0)':d=125:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1920x1080"
        elif style == "pan_right":
            vf = f"zoompan=z=1.3:d=125:x='min(ih/2+{pan_x}*on, ih)':y='ih/2-(ih/zoom/2)':s=1920x1080"
        elif style == "pan_up":
            vf = f"zoompan=z=1.3:d=125:x='iw/2-(iw/zoom/2)':y='min(ih/2-{abs(pan_y)}*on, ih)':s=1920x1080"
        else:
            return False

        cmd = [
            self.settings.ffmpeg_path, "-y",
            "-i", str(src),
            "-vf", vf,
            "-c:v", "libx264", "-crf", "16", "-preset", "veryslow",
            "-tune", "film",
            "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
            str(dst),
        ]
        return self._run_ffmpeg(cmd)

    def _burn_captions(
        self, src: Path, srt_path: Path, dst: Path, requirements: dict
    ) -> bool:
        """Burn SRT captions into the video using ffmpeg subtitles filter."""
        style = requirements.get("caption_style", "bold_white")
        force_style = self._caption_style_string(style)
        cmd = [
            self.settings.ffmpeg_path, "-y",
            "-i", str(src),
            "-vf", f"subtitles={str(srt_path).replace(chr(92), '/')}:force_style='{force_style}'",
            "-c:v", "libx264", "-crf", "16", "-preset", "veryslow",
            "-tune", "film",
            "-c:a", "aac", "-b:a", "320k",
            str(dst),
        ]
        return self._run_ffmpeg(cmd)

    def _caption_style_string(self, style: str) -> str:
        styles = {
            "bold_white": "FontName=Arial,FontSize=20,Bold=1,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,BorderStyle=3,Outline=2,Shadow=1,Alignment=2,MarginV=60",
            "minimal": "FontName=Arial,FontSize=16,Bold=0,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=1,Alignment=2,MarginV=60",
            "yellow": "FontName=Arial,FontSize=20,Bold=1,PrimaryColour=&H00FFFF,OutlineColour=&H000000,BorderStyle=3,Outline=2,Shadow=1,Alignment=2,MarginV=60",
        }
        return styles.get(style, styles["bold_white"])

    # ------------------------------------------------------------------
    # Hook generation — A/B variants
    # ------------------------------------------------------------------

    _HOOK_STYLES = [
        "bold_statement",
        "curiosity_gap",
        "controversial",
        "how_to",
        "number_list",
        "question",
    ]

    def _generate_hook_variants(
        self, clip, requirements: dict, transcript_window: str
    ) -> list[str]:
        """Generate 3-5 hook text variants for A/B testing."""
        if not requirements.get("hook_required", True):
            return []

        from app.services.ai_service import AIService
        ai = AIService()

        platform = requirements.get("platform", "TikTok")
        preferred_style = requirements.get("hook_style", "bold_statement")

        # Pick 3 styles: preferred + 2 alternates
        styles = [preferred_style]
        alternates = [s for s in self._HOOK_STYLES if s != preferred_style]
        import random
        random.shuffle(alternates)
        styles.extend(alternates[:min(4, len(alternates))])

        hooks = []
        for style in styles:
            prompt = f"""Write a short, punchy hook for a {platform} video clip.

Style: {style}
Clip excerpt: {transcript_window[:500]}

Rules:
- Max 8 words
- Attention-grabbing, creates curiosity
- No hashtags, no emojis
- Style: {style}

Return ONLY the hook text."""

            response = ai.complete(prompt, model=self.settings.ai_fast_model)
            if response:
                hook = response.strip().strip('"').strip("'")
                if hook and hook not in hooks:
                    hooks.append(hook)

        self.logger.info(f"Generated {len(hooks)} hook variants: {hooks}")
        return hooks[:5]

    # ------------------------------------------------------------------
    # Voice-over generation
    # ------------------------------------------------------------------

    def _generate_voiceover(self, clip, requirements: dict, tmpdir: str) -> Path | None:
        """Generate TTS voiceover audio using edge-tts."""
        try:
            transcript_window = self._get_transcript_window(clip)
            if not transcript_window:
                self.logger.warning("No transcript available for voiceover")
                return None

            script = transcript_window[:2000]
            voice = requirements.get("voiceover_voice", "en-US-JennyNeural")
            rate = requirements.get("voiceover_rate", "+0%")
            pitch = requirements.get("voiceover_pitch", "+0Hz")

            from app.services.video_processor import VideoProcessor
            output_path = Path(tmpdir) / "voiceover.mp3"
            success = VideoProcessor.generate_voiceover_sync(script, output_path, voice, rate, pitch)

            if success:
                self.logger.info(f"Voiceover generated: {output_path} ({output_path.stat().st_size} bytes)")
                return output_path
            return None

        except Exception as exc:
            self.logger.error(f"Voiceover generation failed: {exc}")
            return None

    def _get_transcript_window(self, clip) -> str:
        try:
            source = clip.source_content
            if not source or not source.transcript:
                return ""
            segments = source.transcript.segments or []
            return " ".join(
                s["text"] for s in segments
                if s.get("start", 0) >= clip.source_start_seconds
                and s.get("end", 0) <= clip.source_end_seconds + 2
            )
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Caption SRT generation
    # ------------------------------------------------------------------

    def _generate_captions_srt(self, clip) -> str | None:
        try:
            source = clip.source_content
            if not source or not source.transcript:
                return None

            segments = source.transcript.segments or []
            relevant = [
                s for s in segments
                if s.get("end", 0) >= clip.source_start_seconds
                and s.get("start", 0) <= clip.source_end_seconds
            ]

            lines = []
            for i, seg in enumerate(relevant, 1):
                start = max(0, seg["start"] - clip.source_start_seconds)
                end = max(0, seg["end"] - clip.source_start_seconds)
                lines.append(f"{i}")
                lines.append(f"{self._ts(start)} --> {self._ts(end)}")
                lines.append(seg["text"].strip())
                lines.append("")

            return "\n".join(lines) if lines else None
        except Exception as exc:
            self.logger.debug(f"SRT generation failed: {exc}")
            return None

    def _ts(self, seconds: float) -> str:
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        ms = int((seconds % 1) * 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------

    def _run_ffmpeg(self, cmd: list) -> bool:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if result.returncode != 0:
                self.logger.warning(f"FFmpeg error: {result.stderr[-300:]}")
                return False
            return True
        except Exception as exc:
            self.logger.error(f"FFmpeg exception: {exc}")
            return False

    def _probe_video(self, path: Path) -> dict:
        import json as _json
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_streams", "-show_format", str(path)],
                capture_output=True, text=True, timeout=30,
            )
            data = _json.loads(result.stdout)
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
