"""
QualityControlAgent — validates clips against campaign requirements.

Checks: duration, resolution, aspect ratio, captions, file size,
audio quality, hook presence. Scores each dimension and produces
a pass/fail decision with detailed notes.
"""
import subprocess
import json
from pathlib import Path
import tempfile

from sqlalchemy.orm import Session

from app.agents.base_agent import AgentResult, BaseAgent


class QualityControlAgent(BaseAgent):
    name = "quality_control"

    def run(self, clip_id: str) -> AgentResult:
        from app.models.clip import Clip, ClipStatus
        from app.core.storage import download_file

        clip = self.db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            return AgentResult.fail(f"Clip {clip_id} not found")

        campaign = clip.campaign
        requirements = campaign.requirements if campaign else {}

        self.logger.info(f"QC check for clip {clip_id}")

        with tempfile.TemporaryDirectory(prefix="clip_qc_") as tmpdir:
            local_path = download_file(
                clip.storage_bucket,
                clip.storage_key,
                Path(tmpdir) / "clip.mp4",
            )

            scores, notes, passed = self._validate(local_path, clip, requirements)

        # Update clip
        clip.scores.update(scores)
        overall = sum(scores.values()) / len(scores) if scores else 0.0
        clip.overall_score = overall
        clip.qc_notes = "; ".join(notes)

        if passed and overall >= self.settings.clip_score_threshold:
            if self.settings.auto_submit:
                clip.status = ClipStatus.QC_PASS
            else:
                clip.status = ClipStatus.AWAITING_APPROVAL
        else:
            clip.status = ClipStatus.QC_FAIL

        self.db.flush()
        self._audit("clip", clip.id, "qc_completed", metadata={
            "passed": passed, "score": overall, "notes": notes
        })

        self.logger.info(
            f"Clip {clip_id} QC: {'PASS' if passed else 'FAIL'} "
            f"score={overall:.2f} notes={notes[:3]}"
        )

        # Telegram: notify with scores + send clip if passed
        try:
            from app.services.telegram_notifier import TelegramNotifier
            tg = TelegramNotifier(self.settings)
            tg.notify_qc_result(clip)
        except Exception as exc:
            self.logger.debug(f"Telegram QC notification skipped: {exc}")

        if passed and overall >= self.settings.clip_score_threshold:
            if self.settings.auto_submit:
                from app.workers.delivery_tasks import create_deliverable
                create_deliverable.apply_async(args=[clip_id], queue="delivery")
            if self.settings.auto_publish:
                from app.workers.publish_tasks import publish_clip
                publish_clip.apply_async(args=[clip_id], queue="publish")
                self.logger.info(f"auto_publish: queued YouTube/social publish for clip {clip_id}")

        return AgentResult.ok({"passed": passed, "score": overall, "notes": notes})

    # ------------------------------------------------------------------

    def _validate(
        self, local_path: Path, clip, requirements: dict
    ) -> tuple[dict, list[str], bool]:
        scores = {}
        notes = []
        failures = []

        # Probe actual file
        probe = self._probe(local_path)
        if not probe:
            return {}, ["ffprobe failed"], False

        duration = probe.get("duration", 0)
        width = probe.get("width", 0)
        height = probe.get("height", 0)
        fps = probe.get("fps", 30)

        # --- Duration ---
        dur_min = requirements.get("duration_min", 15)
        dur_max = requirements.get("duration_max", 180)
        if dur_min <= duration <= dur_max:
            scores["duration"] = 1.0
        elif duration < dur_min:
            scores["duration"] = 0.0
            failures.append(f"Too short: {duration:.1f}s < {dur_min}s minimum")
        else:
            scores["duration"] = 0.3
            notes.append(f"Too long: {duration:.1f}s > {dur_max}s max")

        # --- Resolution ---
        res_str = requirements.get("resolution", "")
        if res_str:
            try:
                req_w, req_h = [int(x) for x in res_str.lower().replace("x", "x").split("x")]
                if width == req_w and height == req_h:
                    scores["resolution"] = 1.0
                elif abs(width - req_w) <= 10 and abs(height - req_h) <= 10:
                    scores["resolution"] = 0.9
                    notes.append(f"Resolution close but not exact: {width}x{height} vs {req_w}x{req_h}")
                else:
                    scores["resolution"] = 0.0
                    failures.append(f"Wrong resolution: {width}x{height} (required {res_str})")
            except Exception:
                scores["resolution"] = 0.8
        else:
            scores["resolution"] = 1.0

        # --- Aspect ratio ---
        aspect = requirements.get("aspect_ratio", "")
        if aspect and width and height:
            try:
                req_w, req_h = [int(x) for x in aspect.split(":")]
                actual_ratio = width / height
                req_ratio = req_w / req_h
                ratio_diff = abs(actual_ratio - req_ratio)
                if ratio_diff < 0.05:
                    scores["aspect_ratio"] = 1.0
                elif ratio_diff < 0.1:
                    scores["aspect_ratio"] = 0.8
                    notes.append(f"Aspect ratio slightly off: {width}x{height}")
                else:
                    scores["aspect_ratio"] = 0.2
                    failures.append(f"Wrong aspect ratio: {width}x{height} (required {aspect})")
            except Exception:
                scores["aspect_ratio"] = 0.8
        else:
            scores["aspect_ratio"] = 1.0

        # --- FPS ---
        req_fps = requirements.get("fps", 30)
        if abs(fps - req_fps) < 1:
            scores["fps"] = 1.0
        else:
            scores["fps"] = 0.7
            notes.append(f"FPS mismatch: {fps:.1f} vs {req_fps}")

        # --- File size ---
        size_mb = local_path.stat().st_size / 1024 / 1024
        max_size_mb = requirements.get("max_file_size_mb", 500)
        if size_mb <= max_size_mb:
            scores["file_size"] = 1.0
        else:
            scores["file_size"] = 0.0
            failures.append(f"File too large: {size_mb:.1f}MB > {max_size_mb}MB")

        # --- Captions ---
        if requirements.get("caption_required", True):
            has_subs = self._has_subtitle_stream(local_path) or clip.captions_srt is not None
            scores["captions"] = 1.0 if has_subs else 0.5
            if not has_subs:
                notes.append("Captions not detected in file")

        # --- Hook ---
        if requirements.get("hook_required", True):
            scores["hook"] = 1.0 if clip.hook_text else 0.6
            if not clip.hook_text:
                notes.append("No hook text generated")

        # --- Audio ---
        has_audio = probe.get("has_audio", True)
        scores["audio"] = 1.0 if has_audio else 0.5
        if not has_audio:
            notes.append("No audio stream detected")

        passed = len(failures) == 0
        all_notes = failures + notes

        return scores, all_notes, passed

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
            self.logger.error(f"ffprobe failed in QC: {exc}")
            return None

    def _has_subtitle_stream(self, path: Path) -> bool:
        try:
            result = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_streams", "-select_streams", "s",
                 str(path)],
                capture_output=True, text=True, timeout=15,
            )
            return "codec_type=subtitle" in result.stdout
        except Exception:
            return False
