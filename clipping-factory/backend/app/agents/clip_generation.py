"""
ClipGenerationAgent — cuts raw clips from source video using ffmpeg.
BATCH MODE: generates 15-30+ clips per source using multiple variants:

1. Multiple duration targets per candidate (15s quick, 30s standard, 60s deep)
2. Overlapping sliding windows to maximise clip count
3. Multiple hook variants per clip (for A/B testing downstream)
"""
import os
import math
import subprocess
import tempfile
from pathlib import Path

from sqlalchemy.orm import Session

from app.agents.base_agent import AgentResult, BaseAgent


# Duration variants to generate per candidate segment
_DURATION_VARIANTS = [15, 30, 45, 60]
# Hook variants per clip (actual hook text generated in EditingAgent)
_HOOK_VARIANTS = ["a", "b", "c"]


class ClipGenerationAgent(BaseAgent):
    name = "clip_generation"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, source_content_id: str) -> AgentResult:
        from app.models.source_content import SourceContent
        from app.models.transcript import Transcript
        from app.models.clip import Clip, ClipStatus
        from app.core.storage import download_file, upload_file

        source = (
            self.db.query(SourceContent)
            .filter(SourceContent.id == source_content_id)
            .first()
        )
        if not source:
            return AgentResult.fail(f"SourceContent {source_content_id} not found")

        transcript = source.transcript
        if not transcript or not transcript.clip_candidates:
            return AgentResult.fail("No clip candidates found — run content analysis first")

        campaign = source.campaign
        requirements = campaign.requirements if campaign else {}
        candidates = transcript.clip_candidates
        source_duration = source.duration_seconds or 0

        self.logger.info(
            f"Batch generating clips for source {source_content_id}: "
            f"{len(candidates)} AI candidates, {source_duration:.0f}s total"
        )

        # Build expanded generation plan
        plan = self._build_generation_plan(
            candidates=candidates,
            source_duration=source_duration,
            requirements=requirements,
        )
        self.logger.info(f"Generation plan: {len(plan)} clip variants to cut")

        clips_created = []
        max_clips = self.settings.max_clips_per_campaign

        with tempfile.TemporaryDirectory(prefix="clip_gen_") as tmpdir:
            source_path = download_file(
                source.storage_bucket,
                source.storage_key,
                Path(tmpdir) / "source.mp4",
            )

            for plan_idx, item in enumerate(plan):
                if len(clips_created) >= max_clips:
                    self.logger.info(f"Reached max clips per campaign ({max_clips})")
                    break
                try:
                    clip = self._generate_clip_variant(
                        source_path=source_path,
                        plan_item=item,
                        source_content_id=source_content_id,
                        campaign_id=campaign.id,
                        source_duration=source_duration,
                        tmpdir=tmpdir,
                        idx=plan_idx,
                    )
                    if clip:
                        clips_created.append(clip.id)
                except Exception as exc:
                    self.logger.error(f"Clip variant {plan_idx} failed: {exc}")
                    continue

        self.logger.info(f"Generated {len(clips_created)} raw clips (plan had {len(plan)} variants)")

        # Trigger editing for each clip (with hook variant metadata)
        for idx, clip_id in enumerate(clips_created):
            from app.workers.video_tasks import edit_clip
            edit_clip.apply_async(args=[clip_id], queue="video")

        return AgentResult.ok({
            "clips_created": clips_created,
            "plan_count": len(plan),
        })

    # ------------------------------------------------------------------
    # Generation plan — expands AI candidates into many clip variants
    # ------------------------------------------------------------------

    def _build_generation_plan(
        self,
        candidates: list[dict],
        source_duration: float,
        requirements: dict,
    ) -> list[dict]:
        """
        Expand the AI candidates into a full generation plan with:
        - Each candidate at multiple duration targets
        - Sliding overlapping windows between candidates
        - Hook variants per window

        Target: 15-30+ clips from a single source video.
        """
        plan = []

        # 1. For each AI candidate, generate at every viable duration
        min_dur = requirements.get("duration_min", 15)
        max_dur = requirements.get("duration_max", 60)

        viable_durations = [d for d in _DURATION_VARIANTS if min_dur <= d <= max_dur]
        if not viable_durations:
            viable_durations = [max(min_dur, 15)]

        for candidate in candidates:
            start = candidate["start"]
            end = candidate["end"]
            available = end - start

            for target_dur in viable_durations:
                if target_dur > available:
                    continue
                # Primary cut: near the start (hook-first approach)
                plan.append({
                    "start": start,
                    "duration": target_dur,
                    "source_candidate_idx": candidates.index(candidate),
                    "score": candidate.get("score", 0.5),
                    "type": "primary",
                    "tags": candidate.get("tags", []),
                })
                # End cut: last N seconds (if enough room)
                if target_dur < available - 2:
                    plan.append({
                        "start": end - target_dur,
                        "duration": target_dur,
                        "source_candidate_idx": candidates.index(candidate),
                        "score": candidate.get("score", 0.5) * 0.9,
                        "type": "tail",
                        "tags": candidate.get("tags", []) + ["tail"],
                    })

        # 2. Add sliding overlapping windows to fill gaps / maximise clips
        if len(candidates) >= 2:
            for i in range(len(candidates) - 1):
                gap_start = candidates[i]["end"]
                gap_end = candidates[i + 1]["start"]
                gap_available = gap_end - gap_start
                if gap_available >= min_dur:
                    mid = (gap_start + gap_end) / 2
                    for target_dur in viable_durations:
                        if target_dur > gap_available:
                            continue
                        window_start = mid - (target_dur / 2)
                        if window_start < 0:
                            window_start = 0
                        plan.append({
                            "start": window_start,
                            "duration": target_dur,
                            "source_candidate_idx": i,
                            "score": 0.6,
                            "type": "transition",
                            "tags": ["transition"],
                        })

        # 3. Sort by score descending, deduplicate overlapping windows
        plan.sort(key=lambda x: x["score"], reverse=True)
        deduped = self._deduplicate_plan(plan, min_gap=3.0)

        # 4. Trim to budget
        max_limit = self.settings.max_clips_per_campaign
        return deduped[:max_limit]

    def _deduplicate_plan(self, plan: list[dict], min_gap: float = 3.0) -> list[dict]:
        """Remove windows that overlap too much with higher-scored ones."""
        kept = []
        for item in plan:
            s1, e1 = item["start"], item["start"] + item["duration"]
            overlaps = False
            for existing in kept:
                s2, e2 = existing["start"], existing["start"] + existing["duration"]
                overlap = max(0, min(e1, e2) - max(s1, s2))
                if overlap > min_gap:
                    overlaps = True
                    break
            if not overlaps:
                kept.append(item)
        return kept

    # ------------------------------------------------------------------
    # Individual clip variant generation
    # ------------------------------------------------------------------

    def _generate_clip_variant(
        self,
        source_path: Path,
        plan_item: dict,
        source_content_id: str,
        campaign_id: str,
        source_duration: float,
        tmpdir: str,
        idx: int,
    ):
        from app.models.clip import Clip, ClipStatus
        from app.core.storage import upload_file

        start = float(plan_item["start"])
        duration = float(plan_item["duration"])
        end = start + duration

        # Bounds validation
        if start < 0 or start > source_duration or end > source_duration or duration <= 0:
            self.logger.warning(
                f"Skipping invalid clip window: start={start:.1f}, end={end:.1f}, "
                f"duration={duration:.1f}s (source_duration={source_duration:.1f}s)"
            )
            return None

        output_filename = f"raw_clip_{idx:03d}_{int(start)}_{int(end)}.mp4"
        output_path = Path(tmpdir) / output_filename

        success = self._ffmpeg_cut(source_path, output_path, start, duration)
        if not success:
            return None
        if not output_path.exists():
            return None

        storage_key = f"clips/{campaign_id}/raw/{output_filename}"
        upload_file(
            output_path,
            self.settings.storage_bucket_clips,
            storage_key,
            content_type="video/mp4",
            metadata={
                "campaign_id": campaign_id,
                "type": "raw",
                "plan_type": plan_item.get("type", "primary"),
                "tags": ",".join(plan_item.get("tags", [])),
            },
        )

        clip = Clip(
            campaign_id=campaign_id,
            source_content_id=source_content_id,
            source_start_seconds=start,
            source_end_seconds=end,
            duration_seconds=duration,
            storage_bucket=self.settings.storage_bucket_clips,
            storage_key=storage_key,
            status=ClipStatus.EDITING,
            overall_score=plan_item.get("score", 0.5),
            scores={
                "content_score": plan_item.get("score", 0.5),
                "variant_type": plan_item.get("type", "primary"),
            },
            version=1,
        )
        self.db.add(clip)
        self.db.flush()

        self._audit("clip", clip.id, "generated", metadata=plan_item)
        self._notify_clip_generated(clip.id, clip.campaign.title if clip.campaign else "Unknown", duration)
        return clip

    def _notify_clip_generated(self, clip_id: str, campaign_title: str, duration: float) -> None:
        """Send Telegram notification when a clip is generated."""
        try:
            from app.services.telegram_notifier import TelegramNotifier
            # Fetch the clip to pass full object for rich notification
            from app.models.clip import Clip
            clip = self.db.query(Clip).filter(Clip.id == clip_id).first()
            if clip:
                tg = TelegramNotifier(self.settings)
                tg.notify_clip_generated(clip)
            else:
                # Fallback: text-only
                tg = TelegramNotifier(self.settings)
                tg.send_message(
                    f"🎬 *New Clip Generated*\n"
                    f"Campaign: {campaign_title[:50]}\n"
                    f"Duration: {duration:.0f}s\n"
                    f"Clip ID: `{clip_id[:8]}`"
                )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # FFmpeg
    # ------------------------------------------------------------------

    def _ffmpeg_cut(
        self, source: Path, output: Path, start: float, duration: float
    ) -> bool:
        """Use ffmpeg stream copy for fast initial cut (no re-encode)."""
        cmd = [
            self.settings.ffmpeg_path,
            "-y",
            "-ss", str(start),
            "-i", str(source),
            "-t", str(duration),
            "-c", "copy",
            "-avoid_negative_ts", "1",
            str(output),
        ]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode != 0:
                self.logger.error(f"ffmpeg cut failed: {result.stderr[-500:]}")
                return False
            return True
        except subprocess.TimeoutExpired:
            self.logger.error("ffmpeg cut timed out")
            return False
        except Exception as exc:
            self.logger.error(f"ffmpeg cut exception: {exc}")
            return False
