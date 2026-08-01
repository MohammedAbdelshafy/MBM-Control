"""
ViralBenchmarkAgent — analyzes and enhances video clips against top viral video benchmarks.

Produces:
- 4-axis Viral Comparison Report (Hook, Content, Tags, Pacing)
- Enriched Viral Tag Suite & Platform Hashtags
- Multi-Platform Optimized Metadata (YouTube Shorts, TikTok, Reels, X)
- Directives for benchmark-driven video editing
"""
from typing import Any
from app.agents.base_agent import AgentResult, BaseAgent
from app.services.viral_comparison_service import ViralComparisonService


class ViralBenchmarkAgent(BaseAgent):
    name = "viral_benchmark"

    def run(self, clip_id: str, niche: str | None = None) -> AgentResult:
        from app.models.clip import Clip
        from app.models.transcript import Transcript

        clip = self.db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            return AgentResult.fail(f"Clip {clip_id} not found")

        self.logger.info(f"Running viral video comparison and enhancement for Clip {clip.id}")

        # Resolve transcript text and niche
        transcript = (
            self.db.query(Transcript)
            .filter(Transcript.source_content_id == clip.source_content_id)
            .first()
        )
        transcript_text = transcript.full_text if transcript else ""

        # Extract transcript segment for this clip's window
        if transcript and transcript.segments:
            window_segments = [
                s.get("text", "")
                for s in transcript.segments
                if s.get("start", 0) >= clip.source_start_seconds and s.get("end", 0) <= clip.source_end_seconds + 2
            ]
            if window_segments:
                transcript_text = " ".join(window_segments)

        campaign = clip.campaign
        target_niche = niche or (campaign.brand_name if campaign and campaign.brand_name else "general_viral")
        if campaign and campaign.requirements and "niche" in campaign.requirements:
            target_niche = campaign.requirements["niche"]

        service = ViralComparisonService()

        # Step 1: Run viral comparison
        comparison_report = service.compare_clip_to_viral(
            transcript_text=transcript_text,
            hook_text=clip.hook_text or transcript_text[:120],
            current_tags=clip.enhanced_tags or [],
            duration_seconds=clip.duration_seconds or (clip.source_end_seconds - clip.source_start_seconds),
            niche=target_niche,
        )

        # Step 2: Generate viral enhancements
        enhancements = service.generate_viral_enhancements(
            transcript_text=transcript_text,
            hook_text=clip.hook_text or transcript_text[:120],
            current_tags=clip.enhanced_tags or [],
            niche=target_niche,
        )

        # Step 3: Persist updates on clip
        clip.viral_benchmark = comparison_report
        clip.enhanced_tags = enhancements["enhanced_tags"]
        clip.platform_metadata = enhancements["platform_metadata"]

        # Update scores dictionary
        scores = dict(clip.scores or {})
        scores["viral_alignment"] = comparison_report["overall_viral_score"] / 100.0
        scores["hook_impact"] = comparison_report["metrics"]["hook_score"] / 100.0
        scores["tag_seo_coverage"] = comparison_report["metrics"]["tag_score"] / 100.0
        clip.scores = scores

        self.db.flush()

        self.logger.info(
            f"Viral benchmark complete for clip {clip.id}: "
            f"Tier = {comparison_report['tier']}, Score = {comparison_report['overall_viral_score']}%"
        )

        self._audit("clip", clip.id, "viral_benchmark_completed", metadata={
            "tier": comparison_report["tier"],
            "score": comparison_report["overall_viral_score"],
            "tags_count": len(clip.enhanced_tags),
        })

        return AgentResult.ok({
            "clip_id": clip.id,
            "overall_viral_score": comparison_report["overall_viral_score"],
            "tier": comparison_report["tier"],
            "metrics": comparison_report["metrics"],
            "enhanced_tags": clip.enhanced_tags,
            "platform_metadata": clip.platform_metadata,
        })
