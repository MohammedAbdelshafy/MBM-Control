"""
ViewsLikesMilestonesAgent — Audits video views and likes milestone achievements
and automatically triggers high-impact system enhancements.

Responsibilities:
1. Audits view counts and like counts across published clips and social posts.
2. Identifies newly unlocked View Milestones (1k, 5k, 10k, 50k, 100k, 250k, 500k, 1M, 5M, 10M)
   and Like Milestones (100, 500, 1k, 5k, 10k, 50k, 100k).
3. System Enhancements triggered on milestones:
   - Multi-Platform Cross-Distribution (distribute top-performing clips to all platforms)
   - Pro Quality Video Filter Enhancement (sharpen, color grade, denoise, upscale)
   - Viral SEO Tag & Metadata Amplification (refresh tags & titles via benchmark profiles)
   - Autonomous Learning Engine Memory Updates (boost winning hook/niche weights)
   - Good-News Telegram & Webhook Milestone Notifications
"""
from typing import Any
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.agents.base_agent import AgentResult, BaseAgent
from app.models.social_post import SocialPost, SocialPostStatus
from app.models.clip import Clip
from app.core.logging_config import get_logger

logger = get_logger("agent.views_likes_milestones")


class ViewsLikesMilestonesAgent(BaseAgent):
    name = "views_likes_milestones"

    VIEW_MILESTONES = [
        {"label": "1K Views", "threshold": 1_000, "enhancement_tier": "starter"},
        {"label": "5K Views", "threshold": 5_000, "enhancement_tier": "starter"},
        {"label": "10K Views", "threshold": 10_000, "enhancement_tier": "bronze"},
        {"label": "50K Views", "threshold": 50_000, "enhancement_tier": "silver"},
        {"label": "100K Views", "threshold": 100_000, "enhancement_tier": "gold"},
        {"label": "250K Views", "threshold": 250_000, "enhancement_tier": "gold"},
        {"label": "500K Views", "threshold": 500_000, "enhancement_tier": "platinum"},
        {"label": "1M Views", "threshold": 1_000_000, "enhancement_tier": "diamond"},
        {"label": "5M Views", "threshold": 5_000_000, "enhancement_tier": "diamond"},
        {"label": "10M Views (YPP Shorts Target)", "threshold": 10_000_000, "enhancement_tier": "legendary"},
    ]

    LIKE_MILESTONES = [
        {"label": "100 Likes", "threshold": 100, "enhancement_tier": "starter"},
        {"label": "500 Likes", "threshold": 500, "enhancement_tier": "bronze"},
        {"label": "1K Likes", "threshold": 1_000, "enhancement_tier": "silver"},
        {"label": "5K Likes", "threshold": 5_000, "enhancement_tier": "gold"},
        {"label": "10K Likes", "threshold": 10_000, "enhancement_tier": "platinum"},
        {"label": "50K Likes", "threshold": 50_000, "enhancement_tier": "diamond"},
        {"label": "100K Likes", "threshold": 100_000, "enhancement_tier": "legendary"},
    ]

    def run(
        self,
        post_id: str | None = None,
        clip_id: str | None = None,
    ) -> AgentResult:
        if self.db is None:
            return AgentResult.fail("Database session unavailable")

        # Query posts to audit
        query = self.db.query(SocialPost).filter(
            SocialPost.status.in_([SocialPostStatus.PUBLISHED, SocialPostStatus.SIMULATED])
        )

        if post_id:
            query = query.filter(SocialPost.id == post_id)
        elif clip_id:
            query = query.filter(SocialPost.clip_id == clip_id)

        posts = query.all()
        if not posts:
            return AgentResult.ok({
                "audited_posts": 0,
                "new_milestones_unlocked": 0,
                "system_enhancements_applied": [],
                "message": "No published posts found to audit."
            })

        milestone_events = []
        enhancements_applied = []

        for post in posts:
            # Load stored unlocked milestones
            current_milestones = list(post.unlocked_milestones or [])
            views = post.views or 0
            likes = post.likes or 0

            newly_unlocked = []

            # Check View Milestones
            for vm in self.VIEW_MILESTONES:
                m_key = f"view_{vm['threshold']}"
                if views >= vm["threshold"] and m_key not in current_milestones:
                    current_milestones.append(m_key)
                    newly_unlocked.append({
                        "type": "views",
                        "label": vm["label"],
                        "threshold": vm["threshold"],
                        "tier": vm["enhancement_tier"],
                        "post_id": post.id,
                        "clip_id": post.clip_id,
                        "platform": post.platform,
                    })

            # Check Like Milestones
            for lm in self.LIKE_MILESTONES:
                m_key = f"like_{lm['threshold']}"
                if likes >= lm["threshold"] and m_key not in current_milestones:
                    current_milestones.append(m_key)
                    newly_unlocked.append({
                        "type": "likes",
                        "label": lm["label"],
                        "threshold": lm["threshold"],
                        "tier": lm["enhancement_tier"],
                        "post_id": post.id,
                        "clip_id": post.clip_id,
                        "platform": post.platform,
                    })

            if newly_unlocked:
                post.unlocked_milestones = current_milestones
                self.db.flush()

                for m_event in newly_unlocked:
                    milestone_events.append(m_event)
                    # Trigger System Enhancements for this milestone
                    applied = self._apply_system_enhancements(post, m_event)
                    enhancements_applied.extend(applied)

        self._audit(
            "views_likes_milestones",
            post_id or clip_id or "global_audit",
            "milestone_audit_completed",
            metadata={
                "audited_posts": len(posts),
                "unlocked_count": len(milestone_events),
                "enhancements_count": len(enhancements_applied),
            }
        )

        return AgentResult.ok({
            "audited_posts": len(posts),
            "new_milestones_unlocked": len(milestone_events),
            "milestones": milestone_events,
            "system_enhancements_applied": enhancements_applied,
        })

    def _apply_system_enhancements(
        self,
        post: SocialPost,
        event: dict,
    ) -> list[str]:
        """Trigger automated system enhancements for milestone posts."""
        enhancements = []
        tier = event.get("tier", "starter")
        clip = post.clip

        # 1. Multi-Platform Cross-Distribution (Silver / Gold / Platinum / Diamond)
        if tier in ["bronze", "silver", "gold", "platinum", "diamond", "legendary"] and clip:
            try:
                from app.agents.multi_platform_delivery import MultiPlatformDeliveryAgent
                mp_agent = MultiPlatformDeliveryAgent(db=self.db)
                mp_res = mp_agent._safe_run(clip_id=clip.id)
                if mp_res.success:
                    enhancements.append(f"multi_platform_cross_distribution_queued:{clip.id}")
            except Exception as exc:
                logger.warning(f"Multi-platform enhancement failed for clip {clip.id}: {exc}")

        # 2. Viral Tag & Title SEO Amplification (Silver+)
        if tier in ["silver", "gold", "platinum", "diamond", "legendary"] and clip:
            try:
                from app.agents.viral_benchmark_agent import ViralBenchmarkAgent
                vb_agent = ViralBenchmarkAgent(db=self.db)
                vb_res = vb_agent._safe_run(clip_id=clip.id)
                if vb_res.success:
                    enhancements.append(f"viral_seo_amplification_applied:{clip.id}")
            except Exception as exc:
                logger.warning(f"Viral SEO amplification failed for clip {clip.id}: {exc}")

        # 3. Pro Quality Video Enhancement (Gold+)
        if tier in ["gold", "platinum", "diamond", "legendary"] and clip:
            try:
                from app.agents.enhancement_agent import EnhancementAgent
                eh_agent = EnhancementAgent(db=self.db)
                eh_res = eh_agent._safe_run(clip_id=clip.id)
                if eh_res.success:
                    enhancements.append(f"pro_video_quality_enhanced:{clip.id}")
            except Exception as exc:
                logger.warning(f"Pro video quality enhancement failed for clip {clip.id}: {exc}")

        # 4. Learning Engine Memory Update
        try:
            from mbm_social.learning_engine import update_performance_from_analytics
            update_performance_from_analytics(
                clip_id=post.clip_id,
                views=post.views,
                ctr=0.08,
                watch_time=35.0,
                subs=int(post.views * 0.005),
                revenue=post.earnings_usd,
            )
            enhancements.append(f"learning_engine_memory_updated:{post.clip_id}")
        except Exception as exc:
            logger.debug(f"Learning engine update skipped: {exc}")

        # 5. Milestone Notification (Good News Only)
        try:
            from app.services.telegram_notifier import TelegramNotifier
            notifier = TelegramNotifier()
            title = f"\U0001f3c6 Milestone Unlocked: {event['label']}!"
            body = (
                f"Clip '{clip.hook_text if clip else post.clip_id}' on {post.platform.upper()} "
                f"just hit {event['label']} ({post.views:,} views, {post.likes:,} likes)! \U0001f525"
            )
            notifier._send(f"{title}\n{body}")
            enhancements.append(f"good_news_milestone_notified:{event['label']}")
        except Exception as exc:
            logger.debug(f"Milestone notification failed: {exc}")

        return enhancements
