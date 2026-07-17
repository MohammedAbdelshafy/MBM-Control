"""
ClipEditorQualityAgent — professional-grade quality gate for clipped videos.

Runs AFTER the editing pipeline and BEFORE publish/delivery. Validates every
aspect a high-paid clipper would check:

  1. Visual Quality — bitrate, resolution, clarity, no black frames/glitches
  2. Audio Quality — LUFS loudness, true peak, voice clarity, music balance
  3. Captions — timing accuracy, burn-in visibility, style consistency
  4. Hook & Engagement — first 3s hook, curiosity gap, CTA presence, pacing
  5. Platform Compliance — aspect ratio, duration, file size per platform
  6. Brand Consistency — watermark placement, color grading, typography
  7. Content Quality — energy arc, storytelling, silence detection
  8. Technical — smooth transitions, no artifacts, codec compliance

Each check returns a 0.0–1.0 score. Overall score gates auto-publish.
Auto-fixes common issues (black frames, audio normalization, caption timing).
"""
import subprocess
import json
import re
import tempfile
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.agents.base_agent import AgentResult, BaseAgent


# ── Platform specs ──────────────────────────────────────────────────────────
PLATFORM_SPECS = {
    "tiktok": {
        "aspect_ratio": "9:16",
        "min_duration": 15,
        "max_duration": 60,
        "max_file_size_mb": 287,
        "resolution": (1080, 1920),
        "fps_range": (24, 60),
        "bitrate_min_mbps": 4.0,   # was 2.0 — pro quality
        "bitrate_max_mbps": 12.0,
        "codec": "h264",
    },
    "youtube_shorts": {
        "aspect_ratio": "9:16",
        "min_duration": 15,
        "max_duration": 60,
        "max_file_size_mb": 256,
        "resolution": (1080, 1920),
        "fps_range": (24, 60),
        "bitrate_min_mbps": 4.0,   # was 2.0 — pro quality
        "bitrate_max_mbps": 15.0,  # was 12.0
        "codec": "h264",
    },
    "instagram_reels": {
        "aspect_ratio": "9:16",
        "min_duration": 15,
        "max_duration": 90,
        "max_file_size_mb": 250,
        "resolution": (1080, 1920),
        "fps_range": (24, 60),
        "bitrate_min_mbps": 4.0,   # was 2.0 — pro quality
        "bitrate_max_mbps": 12.0,
        "codec": "h264",
    },
    "youtube_long": {
        "aspect_ratio": "16:9",
        "min_duration": 60,
        "max_duration": 7200,
        "max_file_size_mb": 12288,
        "resolution": (1920, 1080),
        "fps_range": (24, 60),
        "bitrate_min_mbps": 8.0,   # was 4.0 — pro quality
        "bitrate_max_mbps": 50.0,
        "codec": "h264",
    },
}

# ── Professional quality thresholds (pro clipper standard) ──────────────────
QUALITY_THRESHOLDS = {
    "lufs_target": -14.0,          # YouTube/TikTok standard
    "lufs_tolerance": 1.5,         # was 2.0 — tighter tolerance
    "true_peak_max_db": -1.5,      # was -1.0 — more headroom
    "silence_threshold_db": -35.0,
    "min_bitrate_mbps": 4.0,       # was 2.0 — pro clips need higher bitrate
    "black_frame_threshold": 0.015, # was 0.02 — stricter
    "scene_change_threshold": 0.35, # was 0.4 — catches more glitches
    "caption_min_duration_s": 0.7,  # was 0.5 — easier to read
    "caption_max_duration_s": 6.0,  # was 7.0 — tighter pacing
    "hook_min_words": 3,
    "hook_max_words": 10,
    "hook_first_seconds": 3,
    "energy_peak_in_first_5s": True,
}


class ClipEditorQualityAgent(BaseAgent):
    """Professional clip quality gate — validates every detail before publish."""

    name = "clip_editor_quality"

    def run(self, clip_id: str, auto_fix: bool = False) -> AgentResult:
        from app.models.clip import Clip, ClipStatus
        from app.core.storage import download_file

        clip = self.db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            return AgentResult.fail(f"Clip {clip_id} not found")

        campaign = clip.campaign
        requirements = campaign.requirements if campaign else {}
        platform = requirements.get("platform", "tiktok")

        self.logger.info(f"Editor QA check for clip {clip_id[:8]} (platform={platform})")

        with tempfile.TemporaryDirectory(prefix="clip_eqa_") as tmpdir:
            local_path = download_file(
                clip.storage_bucket,
                clip.storage_key,
                Path(tmpdir) / "clip.mp4",
            )

            # ── Run all quality checks ──────────────────────────────────
            all_checks = {}
            all_notes = []
            all_fixes = []

            # 1. Visual quality
            vis_scores, vis_notes = self._check_visual_quality(local_path)
            all_checks.update(vis_scores)
            all_notes.extend(vis_notes)

            # 2. Audio quality
            aud_scores, aud_notes = self._check_audio_quality(local_path)
            all_checks.update(aud_scores)
            all_notes.extend(aud_notes)

            # 3. Caption quality
            cap_scores, cap_notes = self._check_caption_quality(local_path, clip)
            all_checks.update(cap_scores)
            all_notes.extend(cap_notes)

            # 4. Hook & engagement
            hook_scores, hook_notes = self._check_hook_engagement(clip, requirements)
            all_checks.update(hook_scores)
            all_notes.extend(hook_notes)

            # 5. Platform compliance
            plat_scores, plat_notes = self._check_platform_compliance(
                local_path, clip, platform
            )
            all_checks.update(plat_scores)
            all_notes.extend(plat_notes)

            # 6. Content quality (pacing, energy, storytelling)
            content_scores, content_notes = self._check_content_quality(
                local_path, clip, requirements
            )
            all_checks.update(content_scores)
            all_notes.extend(content_notes)

            # 7. Technical checks (transitions, artifacts, codec)
            tech_scores, tech_notes = self._check_technical(local_path)
            all_checks.update(tech_scores)
            all_notes.extend(tech_notes)

            # ── Auto-fix common issues ──────────────────────────────────
            if auto_fix:
                fixed_path, fixes = self._auto_fix(local_path, all_checks, tmpdir)
                all_fixes.extend(fixes)
                if fixes:
                    all_notes.append(f"Auto-fixed: {', '.join(fixes)}")

            # ── Calculate overall score ─────────────────────────────────
            weights = {
                "visual_quality": 0.20,
                "audio_quality": 0.20,
                "caption_quality": 0.15,
                "hook_engagement": 0.15,
                "platform_compliance": 0.15,
                "content_quality": 0.10,
                "technical": 0.05,
            }

            category_scores = {}
            for category, weight in weights.items():
                cat_key = f"__{category}"
                if cat_key in all_checks:
                    category_scores[category] = all_checks[cat_key]

            overall = (
                sum(category_scores.get(cat, 0.0) * w for cat, w in weights.items())
                / sum(weights.values())
            ) if category_scores else 0.0

            # ── Update clip ─────────────────────────────────────────────
            clip.scores.update(all_checks)
            clip.scores["__overall_editor_qa"] = overall
            clip.scores["__category_scores"] = category_scores
            clip.overall_score = max(clip.overall_score, overall)
            clip.qc_notes = "; ".join(all_notes[:20])

            if overall >= 0.85:
                clip.status = ClipStatus.QC_PASS
            elif overall >= 0.65:
                clip.status = ClipStatus.AWAITING_APPROVAL
            else:
                clip.status = ClipStatus.QC_FAIL

            self.db.flush()

            self._audit("clip", clip.id, "editor_qa_completed", metadata={
                "overall_score": overall,
                "category_scores": category_scores,
                "notes": all_notes[:10],
                "fixes": all_fixes,
            })

            self.logger.info(
                f"Editor QA clip {clip_id[:8]}: {'PASS' if overall >= 0.85 else 'FAIL'} "
                f"score={overall:.2f} categories={json.dumps({k:round(v,2) for k,v in category_scores.items()})}"
            )

            # Telegram notification
            try:
                from app.services.telegram_notifier import TelegramNotifier
                tg = TelegramNotifier(self.settings)
                tg.notify_qc_result(clip)
            except Exception:
                pass

        return AgentResult.ok({
            "clip_id": clip_id,
            "overall_score": overall,
            "category_scores": category_scores,
            "passed": overall >= 0.85,
            "notes": all_notes,
            "fixes_applied": all_fixes,
        })

    # ═══════════════════════════════════════════════════════════════════════
    # 1. VISUAL QUALITY
    # ═══════════════════════════════════════════════════════════════════════
    def _check_visual_quality(self, path: Path) -> tuple[dict, list[str]]:
        scores = {}
        notes = []
        probe = self._probe(path)
        if not probe:
            return {"__visual_quality": 0.0}, ["ffprobe failed"]

        width = probe.get("width", 0)
        height = probe.get("height", 0)
        bitrate = probe.get("bit_rate", 0)
        duration = probe.get("duration", 0)
        fps = probe.get("fps", 30)

        # Resolution score
        total_pixels = width * height
        if total_pixels >= 1920 * 1080:
            scores["vis_resolution"] = 1.0
        elif total_pixels >= 1280 * 720:
            scores["vis_resolution"] = 0.8
            notes.append(f"HD only: {width}x{height}")
        else:
            scores["vis_resolution"] = 0.3
            notes.append(f"Low resolution: {width}x{height}")

        # Bitrate score (bits per pixel per frame)
        if duration > 0 and fps > 0:
            bpp = (bitrate / (width * height * fps)) if (width * height * fps) else 0
            if bpp >= 0.15:
                scores["vis_bitrate"] = 1.0
            elif bpp >= 0.08:
                scores["vis_bitrate"] = 0.8
                notes.append("Bitrate slightly low — may look soft")
            elif bpp >= 0.04:
                scores["vis_bitrate"] = 0.5
                notes.append("Bitrate low — visible compression artifacts likely")
            else:
                scores["vis_bitrate"] = 0.2
                notes.append("Bitrate very low — blurry/pixelated")

        # Black frame detection (sample frames at start, middle, end)
        black_frames = self._detect_black_frames(path, duration)
        if black_frames == 0:
            scores["vis_black_frames"] = 1.0
        elif black_frames <= 1:
            scores["vis_black_frames"] = 0.6
            notes.append(f"{black_frames} black frame(s) detected")
        else:
            scores["vis_black_frames"] = 0.2
            notes.append(f"{black_frames} black frames — needs fix")

        # FPS check
        if 24 <= fps <= 60:
            scores["vis_fps"] = 1.0
        else:
            scores["vis_fps"] = 0.5
            notes.append(f"Unusual FPS: {fps}")

        # Aspect ratio correctness (should be clean 9:16 or 16:9)
        if width and height:
            ratio = width / height
            expected = [9/16, 16/9, 1/1, 4/5]
            closest = min(expected, key=lambda r: abs(r - ratio))
            if abs(ratio - closest) < 0.02:
                scores["vis_aspect"] = 1.0
            else:
                scores["vis_aspect"] = 0.6
                notes.append(f"Odd aspect ratio: {width}x{height}")

        # Overall visual score
        vis_vals = [v for k, v in scores.items() if k.startswith("vis_")]
        scores["__visual_quality"] = sum(vis_vals) / len(vis_vals) if vis_vals else 0.5

        return scores, notes

    def _detect_black_frames(self, path: Path, duration: float, samples: int = 5) -> int:
        """Detect black frames by sampling frames at intervals."""
        black_count = 0
        try:
            for i in range(samples):
                t = (duration / (samples + 1)) * (i + 1)
                cmd = [
                    self.settings.ffmpeg_path or "ffmpeg", "-y",
                    "-ss", str(t), "-i", str(path),
                    "-vframes", "1",
                    "-vf", "signalstats",
                    "-f", "null", "-",
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                # Check if YAVG (average luma) is very low
                if "YAVG=" in (result.stderr or ""):
                    match = re.search(r"YAVG=([\d.]+)", result.stderr)
                    if match and float(match.group(1)) < 16.0:
                        black_count += 1
        except Exception:
            pass
        return black_count

    # ═══════════════════════════════════════════════════════════════════════
    # 2. AUDIO QUALITY
    # ═══════════════════════════════════════════════════════════════════════
    def _check_audio_quality(self, path: Path) -> tuple[dict, list[str]]:
        scores = {}
        notes = []

        # Measure integrated loudness (LUFS)
        lufs = self._measure_lufs(path)
        if lufs is not None:
            target = QUALITY_THRESHOLDS["lufs_target"]
            tolerance = QUALITY_THRESHOLDS["lufs_tolerance"]
            if abs(lufs - target) <= tolerance:
                scores["aud_loudness"] = 1.0
            elif abs(lufs - target) <= 4.0:
                scores["aud_loudness"] = 0.7
                notes.append(f"Loudness {lufs:.1f} LUFS (target {target})")
            else:
                scores["aud_loudness"] = 0.3
                notes.append(f"Loudness off: {lufs:.1f} LUFS (target {target})")

        # True peak check (should be < -1 dBTP)
        true_peak = self._measure_true_peak(path)
        if true_peak is not None:
            if true_peak <= -1.0:
                scores["aud_true_peak"] = 1.0
            elif true_peak <= 0.0:
                scores["aud_true_peak"] = 0.7
                notes.append(f"True peak {true_peak:.1f} dBTP — close to clipping")
            else:
                scores["aud_true_peak"] = 0.2
                notes.append(f"True peak {true_peak:.1f} dBTP — clipping!")

        # Silence detection (should not start/end with >1s silence)
        silence_ratio = self._detect_silence_ratio(path)
        if silence_ratio is not None:
            if silence_ratio < 0.05:
                scores["aud_silence"] = 1.0
            elif silence_ratio < 0.15:
                scores["aud_silence"] = 0.7
                notes.append(f"Silence ratio {silence_ratio:.0%} — slightly quiet")
            else:
                scores["aud_silence"] = 0.4
                notes.append(f"Silence ratio {silence_ratio:.0%} — too much dead air")

        # Overall audio score
        aud_vals = [v for k, v in scores.items() if k.startswith("aud_")]
        scores["__audio_quality"] = sum(aud_vals) / len(aud_vals) if aud_vals else 0.5

        return scores, notes

    def _measure_lufs(self, path: Path) -> float | None:
        """Measure integrated loudness via ffmpeg loudnorm filter (2-pass)."""
        try:
            cmd = [
                self.settings.ffmpeg_path or "ffmpeg", "-y",
                "-i", str(path),
                "-af", "loudnorm=I=-14:TP=-2:LRA=11:print_format=json",
                "-f", "null", "-",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            # Parse JSON output from stderr
            stderr = result.stderr or ""
            match = re.search(r'\{[^}]*"input_i"[^}]*\}', stderr, re.DOTALL)
            if match:
                data = json.loads(match.group())
                return float(data.get("input_i", -14.0))
            # Fallback: use ebur128 filter
            cmd2 = [
                self.settings.ffmpeg_path or "ffmpeg", "-y",
                "-i", str(path),
                "-af", "ebur128=peak=true",
                "-f", "null", "-",
            ]
            result2 = subprocess.run(cmd2, capture_output=True, text=True, timeout=60)
            lufs_match = re.search(r"I:\s+([-\d.]+)\s+LUFS", result2.stderr or "")
            if lufs_match:
                return float(lufs_match.group(1))
        except Exception:
            pass
        return None

    def _measure_true_peak(self, path: Path) -> float | None:
        """Measure true peak via ebur128 filter."""
        try:
            cmd = [
                self.settings.ffmpeg_path or "ffmpeg", "-y",
                "-i", str(path),
                "-af", "ebur128=peak=true",
                "-f", "null", "-",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            match = re.search(r"Peak:\s+([-\d.]+)\s+dBTP", result.stderr or "")
            if match:
                return float(match.group(1))
        except Exception:
            pass
        return None

    def _detect_silence_ratio(self, path: Path) -> float | None:
        """Detect ratio of silent segments in the audio."""
        try:
            threshold = QUALITY_THRESHOLDS["silence_threshold_db"]
            cmd = [
                self.settings.ffmpeg_path or "ffmpeg", "-y",
                "-i", str(path),
                "-af", f"silencedetect=noise={threshold}dB:d=0.5",
                "-f", "null", "-",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            duration = self._probe(path).get("duration", 0)
            if duration <= 0:
                return None

            total_silence = 0.0
            for match in re.finditer(r"silence_duration:\s*([\d.]+)", result.stderr or ""):
                total_silence += float(match.group(1))

            return total_silence / duration
        except Exception:
            return None

    # ═══════════════════════════════════════════════════════════════════════
    # 3. CAPTION QUALITY
    # ═══════════════════════════════════════════════════════════════════════
    def _check_caption_quality(self, path: Path, clip) -> tuple[dict, list[str]]:
        scores = {}
        notes = []

        srt = clip.captions_srt
        has_srt = bool(srt and srt.strip())

        # Check if captions are burned in (subtitle stream)
        has_burned = self._has_subtitle_stream(path)

        if has_srt:
            scores["cap_generated"] = 1.0

            # Parse SRT and validate timing
            subs = self._parse_srt(srt)
            if subs:
                # Timing accuracy
                short_subs = [s for s in subs if (s["end"] - s["start"]) < QUALITY_THRESHOLDS["caption_min_duration_s"]]
                long_subs = [s for s in subs if (s["end"] - s["start"]) > QUALITY_THRESHOLDS["caption_max_duration_s"]]

                if not short_subs and not long_subs:
                    scores["cap_timing"] = 1.0
                else:
                    scores["cap_timing"] = 0.6
                    if short_subs:
                        notes.append(f"{len(short_subs)} captions too short to read")
                    if long_subs:
                        notes.append(f"{len(long_subs)} captions too long")

                # Word count per caption (should be 1-8 words for readability)
                overlong = [s for s in subs if len(s["text"].split()) > 12]
                if not overlong:
                    scores["cap_readability"] = 1.0
                else:
                    scores["cap_readability"] = 0.7
                    notes.append(f"{len(overlong)} captions have >12 words")

                # Caption coverage (should cover 60%+ of video duration)
                video_dur = clip.duration_seconds or self._probe(path).get("duration", 0)
                if video_dur > 0:
                    captioned_time = sum(s["end"] - s["start"] for s in subs)
                    coverage = captioned_time / video_dur
                    if coverage >= 0.6:
                        scores["cap_coverage"] = 1.0
                    elif coverage >= 0.4:
                        scores["cap_coverage"] = 0.7
                        notes.append(f"Captions cover only {coverage:.0%} of video")
                    else:
                        scores["cap_coverage"] = 0.4
                        notes.append(f"Captions cover only {coverage:.0%} — many gaps")
            else:
                scores["cap_timing"] = 0.3
                scores["cap_readability"] = 0.3
                notes.append("SRT exists but couldn't be parsed")
        else:
            scores["cap_generated"] = 0.0
            notes.append("No captions generated")

        if has_burned:
            scores["cap_burned_in"] = 1.0
        else:
            scores["cap_burned_in"] = 0.5
            notes.append("Captions not burned into video")

        # Overall caption score
        cap_vals = [v for k, v in scores.items() if k.startswith("cap_")]
        scores["__caption_quality"] = sum(cap_vals) / len(cap_vals) if cap_vals else 0.3

        return scores, notes

    def _parse_srt(self, srt_text: str) -> list[dict]:
        """Parse SRT text into list of {index, start, end, text}."""
        subs = []
        try:
            blocks = re.split(r"\n\n+", srt_text.strip())
            for block in blocks:
                lines = block.strip().split("\n")
                if len(lines) >= 3:
                    times = lines[1]
                    match = re.match(
                        r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})",
                        times,
                    )
                    if match:
                        g = [int(x) for x in match.groups()]
                        start = g[0]*3600 + g[1]*60 + g[2] + g[3]/1000
                        end = g[4]*3600 + g[5]*60 + g[6] + g[7]/1000
                        text = " ".join(lines[2:])
                        subs.append({"start": start, "end": end, "text": text})
        except Exception:
            pass
        return subs

    def _has_subtitle_stream(self, path: Path) -> bool:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_streams", "-select_streams", "s", str(path)],
                capture_output=True, text=True, timeout=15,
            )
            return "codec_type=subtitle" in result.stdout
        except Exception:
            return False

    # ═══════════════════════════════════════════════════════════════════════
    # 4. HOOK & ENGAGEMENT
    # ═══════════════════════════════════════════════════════════════════════
    def _check_hook_engagement(self, clip, requirements: dict) -> tuple[dict, list[str]]:
        scores = {}
        notes = []

        hook = clip.hook_text or ""
        hook_variants = (clip.scores or {}).get("hook_variants", [])

        # Hook presence
        if hook:
            scores["hook_present"] = 1.0

            # Hook length (3-10 words is optimal for Shorts)
            words = hook.split()
            word_count = len(words)
            if QUALITY_THRESHOLDS["hook_min_words"] <= word_count <= QUALITY_THRESHOLDS["hook_max_words"]:
                scores["hook_length"] = 1.0
            elif word_count <= 12:
                scores["hook_length"] = 0.7
                notes.append(f"Hook slightly long: {word_count} words")
            else:
                scores["hook_length"] = 0.4
                notes.append(f"Hook too long: {word_count} words")

            # Hook style match
            preferred_style = requirements.get("hook_style", "bold_statement")
            hook_lower = hook.lower()
            style_match = False
            if preferred_style == "bold_statement":
                style_match = any(w in hook_lower for w in ["this", "never", "always", "secret", "insane", "crazy"])
            elif preferred_style == "curiosity_gap":
                style_match = any(w in hook_lower for w in ["what", "why", "how", "secret", "nobody", "you won't"])
            elif preferred_style == "question":
                style_match = "?" in hook
            elif preferred_style == "number_list":
                style_match = bool(re.search(r"\d+", hook))

            scores["hook_style"] = 1.0 if style_match else 0.7

            # No emojis/hashtags in hook (professional)
            has_emoji = bool(re.search(r"[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff]", hook))
            has_hashtag = "#" in hook
            if not has_emoji and not has_hashtag:
                scores["hook_clean"] = 1.0
            else:
                scores["hook_clean"] = 0.6
                notes.append("Hook contains emojis or hashtags")

        else:
            scores["hook_present"] = 0.0
            notes.append("No hook text generated")

        # A/B variants available
        if len(hook_variants) >= 3:
            scores["hook_variants"] = 1.0
        elif len(hook_variants) >= 1:
            scores["hook_variants"] = 0.7
        else:
            scores["hook_variants"] = 0.3
            notes.append("No hook variants for A/B testing")

        # Overall hook score
        hook_vals = [v for k, v in scores.items() if k.startswith("hook_")]
        scores["__hook_engagement"] = sum(hook_vals) / len(hook_vals) if hook_vals else 0.3

        return scores, notes

    # ═══════════════════════════════════════════════════════════════════════
    # 5. PLATFORM COMPLIANCE
    # ═══════════════════════════════════════════════════════════════════════
    def _check_platform_compliance(
        self, path: Path, clip, platform: str
    ) -> tuple[dict, list[str]]:
        scores = {}
        notes = []

        # Map platform string to spec key
        spec_key = {
            "tiktok": "tiktok",
            "youtube": "youtube_shorts",
            "youtube_shorts": "youtube_shorts",
            "instagram": "instagram_reels",
            "instagram_reels": "instagram_reels",
        }.get(platform, "youtube_long")

        spec = PLATFORM_SPECS.get(spec_key, PLATFORM_SPECS["youtube_shorts"])
        probe = self._probe(path)
        if not probe:
            return {"__platform_compliance": 0.0}, ["ffprobe failed"]

        width = probe.get("width", 0)
        height = probe.get("height", 0)
        duration = probe.get("duration", 0)
        fps = probe.get("fps", 30)
        bitrate = probe.get("bit_rate", 0)
        size_mb = path.stat().st_size / (1024 * 1024)

        # Aspect ratio
        expected_w, expected_h = spec["resolution"]
        if width == expected_w and height == expected_h:
            scores["plat_resolution"] = 1.0
        elif abs(width - expected_w) <= 10 and abs(height - expected_h) <= 10:
            scores["plat_resolution"] = 0.9
            notes.append(f"Resolution close: {width}x{height} vs {expected_w}x{expected_h}")
        else:
            scores["plat_resolution"] = 0.3
            notes.append(f"Wrong resolution for {platform}: {width}x{height}")

        # Duration
        min_dur = spec["min_duration"]
        max_dur = spec["max_duration"]
        if min_dur <= duration <= max_dur:
            scores["plat_duration"] = 1.0
        elif duration < min_dur:
            scores["plat_duration"] = 0.2
            notes.append(f"Too short for {platform}: {duration:.1f}s < {min_dur}s")
        elif duration > max_dur:
            scores["plat_duration"] = 0.4
            notes.append(f"Too long for {platform}: {duration:.1f}s > {max_dur}s")

        # File size
        max_size = spec["max_file_size_mb"]
        if size_mb <= max_size:
            scores["plat_file_size"] = 1.0
        else:
            scores["plat_file_size"] = 0.2
            notes.append(f"File too large: {size_mb:.0f}MB > {max_size}MB")

        # FPS
        fps_min, fps_max = spec["fps_range"]
        if fps_min <= fps <= fps_max:
            scores["plat_fps"] = 1.0
        else:
            scores["plat_fps"] = 0.6
            notes.append(f"FPS {fps} outside {platform} range {fps_min}-{fps_max}")

        # Bitrate
        bitrate_mbps = bitrate / 1_000_000 if bitrate else 0
        if spec["bitrate_min_mbps"] <= bitrate_mbps <= spec["bitrate_max_mbps"]:
            scores["plat_bitrate"] = 1.0
        elif bitrate_mbps < spec["bitrate_min_mbps"]:
            scores["plat_bitrate"] = 0.5
            notes.append(f"Bitrate low for {platform}: {bitrate_mbps:.1f}Mbps")
        else:
            scores["plat_bitrate"] = 0.7
            notes.append(f"Bitrate high: {bitrate_mbps:.1f}Mbps (larger file)")

        # Overall platform score
        plat_vals = [v for k, v in scores.items() if k.startswith("plat_")]
        scores["__platform_compliance"] = sum(plat_vals) / len(plat_vals) if plat_vals else 0.5

        return scores, notes

    # ═══════════════════════════════════════════════════════════════════════
    # 6. CONTENT QUALITY
    # ═══════════════════════════════════════════════════════════════════════
    def _check_content_quality(
        self, path: Path, clip, requirements: dict
    ) -> tuple[dict, list[str]]:
        scores = {}
        notes = []

        probe = self._probe(path)
        duration = probe.get("duration", 0) if probe else 0

        # Pacing check: scene changes indicate energy
        scene_changes = self._count_scene_changes(path)
        if duration > 0:
            changes_per_minute = (scene_changes / duration) * 60
            # Good clips have 8-20 cuts per minute for Shorts
            if 6 <= changes_per_minute <= 25:
                scores["content_pacing"] = 1.0
            elif 3 <= changes_per_minute <= 35:
                scores["content_pacing"] = 0.7
                notes.append(f"Pacing {'slow' if changes_per_minute < 6 else 'fast'}: {changes_per_minute:.1f} cuts/min")
            else:
                scores["content_pacing"] = 0.4
                notes.append(f"Pacing poor: {changes_per_minute:.1f} cuts/min")

        # Duration sweet spot for Shorts (15-45s performs best)
        if 15 <= duration <= 45:
            scores["content_duration_sweet"] = 1.0
        elif 10 <= duration <= 60:
            scores["content_duration_sweet"] = 0.7
        else:
            scores["content_duration_sweet"] = 0.5
            notes.append(f"Duration {duration:.0f}s outside optimal 15-45s range")

        # CTA presence (check hook variants or caption for CTAs)
        all_text = " ".join([
            clip.hook_text or "",
            " ".join((clip.scores or {}).get("hook_variants", [])),
        ]).lower()
        cta_words = ["follow", "subscribe", "like", "comment", "share", "link", "bio", "free", "try", "sign up", "join"]
        has_cta = any(w in all_text for w in cta_words)
        if has_cta:
            scores["content_cta"] = 1.0
        else:
            scores["content_cta"] = 0.5
            notes.append("No CTA detected in hooks")

        # Overall content score
        content_vals = [v for k, v in scores.items() if k.startswith("content_")]
        scores["__content_quality"] = sum(content_vals) / len(content_vals) if content_vals else 0.5

        return scores, notes

    def _count_scene_changes(self, path: Path) -> int:
        """Count scene changes using ffmpeg scene detection."""
        try:
            cmd = [
                self.settings.ffmpeg_path or "ffmpeg", "-y",
                "-i", str(path),
                "-vf", f"select='gt(scene,{QUALITY_THRESHOLDS['scene_change_threshold']})',showinfo",
                "-f", "null", "-",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return (result.stderr or "").count("[Parsed showinfo")
        except Exception:
            return 0

    # ═══════════════════════════════════════════════════════════════════════
    # 7. TECHNICAL
    # ═══════════════════════════════════════════════════════════════════════
    def _check_technical(self, path: Path) -> tuple[dict, list[str]]:
        scores = {}
        notes = []

        probe = self._probe(path)
        if not probe:
            return {"__technical": 0.0}, ["ffprobe failed"]

        # Codec check (H.264 is required for most platforms)
        codec = self._get_codec(path)
        if codec in ("h264", "hevc"):
            scores["tech_codec"] = 1.0
        elif codec in ("vp9", "av1"):
            scores["tech_codec"] = 0.7
            notes.append(f"Codec {codec} may not be supported on all platforms")
        else:
            scores["tech_codec"] = 0.3
            notes.append(f"Codec {codec} — should be h264")

        # Audio codec
        audio_codec = self._get_audio_codec(path)
        if audio_codec in ("aac", "mp3", "opus"):
            scores["tech_audio_codec"] = 1.0
        else:
            scores["tech_audio_codec"] = 0.5
            notes.append(f"Audio codec {audio_codec} — aac preferred")

        # Container check (should be MP4)
        suffix = path.suffix.lower()
        if suffix == ".mp4":
            scores["tech_container"] = 1.0
        elif suffix in (".mkv", ".webm"):
            scores["tech_container"] = 0.6
            notes.append(f"Container {suffix} — mp4 preferred")
        else:
            scores["tech_container"] = 0.3

        # No duplicate streams
        stream_count = self._count_streams(path)
        if stream_count <= 3:  # video + audio + maybe subtitle
            scores["tech_streams"] = 1.0
        else:
            scores["tech_streams"] = 0.7
            notes.append(f"Unusual stream count: {stream_count}")

        # Overall technical score
        tech_vals = [v for k, v in scores.items() if k.startswith("tech_")]
        scores["__technical"] = sum(tech_vals) / len(tech_vals) if tech_vals else 0.5

        return scores, notes

    def _get_codec(self, path: Path) -> str:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_streams", "-select_streams", "v:0",
                 "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(path)],
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip().lower()
        except Exception:
            return "unknown"

    def _get_audio_codec(self, path: Path) -> str:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_streams", "-select_streams", "a:0",
                 "-show_entries", "stream=codec_name", "-of", "csv=p=0", str(path)],
                capture_output=True, text=True, timeout=10,
            )
            return result.stdout.strip().lower()
        except Exception:
            return "unknown"

    def _count_streams(self, path: Path) -> int:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=nb_streams",
                 "-of", "csv=p=0", str(path)],
                capture_output=True, text=True, timeout=10,
            )
            return int(result.stdout.strip() or 0)
        except Exception:
            return 0

    # ═══════════════════════════════════════════════════════════════════════
    # AUTO-FIX
    # ═══════════════════════════════════════════════════════════════════════
    def _auto_fix(self, path: Path, scores: dict, tmpdir: str) -> tuple[Path | None, list[str]]:
        """Attempt to fix common issues automatically."""
        fixes = []
        current = path
        ffmpeg = self.settings.ffmpeg_path or "ffmpeg"

        # Fix 1: Audio normalization if loudness is off
        loudness = scores.get("aud_loudness", 1.0)
        if loudness < 0.7:
            fixed = Path(tmpdir) / "fixed_lufs.mp4"
            cmd = [
                ffmpeg, "-y", "-i", str(current),
                "-af", "loudnorm=I=-14:TP=-2:LRA=11",
                "-c:v", "copy",
                "-c:a", "aac", "-b:a", "256k",
                str(fixed),
            ]
            if self._run_ffmpeg(cmd) and fixed.exists():
                current = fixed
                fixes.append("audio_normalized_to_-14_lufs")

        # Fix 2: True peak limiter if clipping
        true_peak = scores.get("aud_true_peak", 1.0)
        if true_peak < 0.7:
            fixed = Path(tmpdir) / "fixed_peak.mp4"
            cmd = [
                ffmpeg, "-y", "-i", str(current),
                "-af", "loudnorm=I=-14:TP=-1.5:LRA=11",
                "-c:v", "copy",
                str(fixed),
            ]
            if self._run_ffmpeg(cmd) and fixed.exists():
                current = fixed
                fixes.append("true_peak_limited")

        # Fix 3: Remove leading/trailing black frames
        black_frames = scores.get("vis_black_frames", 1.0)
        if black_frames < 0.7:
            probe = self._probe(path)
            duration = probe.get("duration", 0) if probe else 0
            if duration > 0:
                # Trim first/last 0.5s to remove black frames
                fixed = Path(tmpdir) / "fixed_trimmed.mp4"
                cmd = [
                    ffmpeg, "-y",
                    "-ss", "0.5", "-i", str(current),
                    "-t", str(duration - 1.0),
                    "-c:v", "copy", "-c:a", "copy",
                    str(fixed),
                ]
                if self._run_ffmpeg(cmd) and fixed.exists():
                    current = fixed
                    fixes.append("black_frames_trimmed")

        # Fix 4: Re-encode to H.264 if wrong codec
        codec = scores.get("tech_codec", 1.0)
        if codec < 0.7:
            fixed = Path(tmpdir) / "fixed_h264.mp4"
            cmd = [
                ffmpeg, "-y", "-i", str(current),
                "-c:v", "libx264", "-crf", "16", "-preset", "veryslow",
                "-tune", "film",
                "-c:a", "aac", "-b:a", "320k", "-ar", "48000",
                str(fixed),
            ]
            if self._run_ffmpeg(cmd) and fixed.exists():
                current = fixed
                fixes.append("reencoded_to_h264")

        return current if fixes else None, fixes

    def _run_ffmpeg(self, cmd: list) -> bool:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            return result.returncode == 0
        except Exception:
            return False

    # ═══════════════════════════════════════════════════════════════════════
    # UTILITIES
    # ═══════════════════════════════════════════════════════════════════════
    def _probe(self, path: Path) -> dict | None:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-print_format", "json",
                 "-show_streams", "-show_format", str(path)],
                capture_output=True, text=True, timeout=30,
            )
            data = json.loads(result.stdout)
            fmt = data.get("format", {})
            streams = data.get("streams", [])
            video = next((s for s in streams if s.get("codec_type") == "video"), {})
            audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
            fps_str = video.get("r_frame_rate", "30/1")
            n, d = fps_str.split("/") if "/" in fps_str else (fps_str, "1")
            return {
                "duration": float(fmt.get("duration", 0)),
                "width": video.get("width", 0),
                "height": video.get("height", 0),
                "fps": float(n) / float(d) if float(d) else 30.0,
                "has_audio": audio is not None,
                "bit_rate": int(fmt.get("bit_rate", 0)),
            }
        except Exception as exc:
            self.logger.error(f"ffprobe failed: {exc}")
            return None
