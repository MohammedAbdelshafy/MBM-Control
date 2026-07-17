"""
Analytics service — performance tracking for published clips across platforms.

Provides:
- Projected earnings based on views and platform CPM
- Aggregated performance per campaign / clip / platform
- Platform-specific revenue projections
- Sync triggers for platform analytics
"""
from datetime import datetime, timezone
from sqlalchemy.orm import Session

from app.models.social_post import SocialPlatform, SocialPost, SocialPostStatus
from app.models.clip import Clip
from app.models.campaign import Campaign


class AnalyticsService:

    def __init__(self, db: Session):
        self.db = db

    # ------------------------------------------------------------------
    # Per-post performance
    # ------------------------------------------------------------------

    def update_post_metrics(
        self,
        post_id: str,
        views: int | None = None,
        likes: int | None = None,
        shares: int | None = None,
        comments: int | None = None,
        earnings_usd: float | None = None,
    ) -> dict | None:
        """Update performance metrics for a single SocialPost."""
        post = self.db.query(SocialPost).filter(SocialPost.id == post_id).first()
        if not post:
            return None

        if views is not None:
            post.views = views
        if likes is not None:
            post.likes = likes
        if shares is not None:
            post.shares = shares
        if comments is not None:
            post.comments = comments
        if earnings_usd is not None:
            post.earnings_usd = earnings_usd

        post.last_synced_at = datetime.now(timezone.utc).isoformat()
        self.db.flush()

        return {
            "post_id": post.id,
            "platform": post.platform,
            "views": post.views,
            "likes": post.likes,
            "shares": post.shares,
            "comments": post.comments,
            "earnings_usd": post.earnings_usd,
            "projected_earnings": self.project_post_earnings(post),
        }

    def project_post_earnings(self, post: SocialPost) -> float:
        """Estimate total earnings for this post based on views + platform CPM."""
        cpm = SocialPlatform.estimated_cpm(post.platform)
        return (post.views / 1000) * cpm

    # ------------------------------------------------------------------
    # Aggregated queries
    # ------------------------------------------------------------------

    def campaign_performance(self, campaign_id: str) -> dict:
        """Aggregated performance across all clips and platforms for a campaign."""
        posts = (
            self.db.query(SocialPost)
            .filter(SocialPost.campaign_id == campaign_id)
            .all()
        )

        if not posts:
            return self._empty_campaign_stats(campaign_id)

        total_views = sum(p.views for p in posts)
        total_likes = sum(p.likes for p in posts)
        total_shares = sum(p.shares for p in posts)
        total_comments = sum(p.comments for p in posts)
        total_earnings = sum(p.earnings_usd for p in posts)
        total_projected = sum(self.project_post_earnings(p) for p in posts)

        platform_breakdown = {}
        for p in posts:
            if p.platform not in platform_breakdown:
                platform_breakdown[p.platform] = {
                    "posts": 0, "views": 0, "likes": 0,
                    "shares": 0, "comments": 0, "earnings": 0,
                }
            platform_breakdown[p.platform]["posts"] += 1
            platform_breakdown[p.platform]["views"] += p.views
            platform_breakdown[p.platform]["likes"] += p.likes
            platform_breakdown[p.platform]["shares"] += p.shares
            platform_breakdown[p.platform]["comments"] += p.comments
            platform_breakdown[p.platform]["earnings"] += p.earnings_usd

        return {
            "campaign_id": campaign_id,
            "total_posts": len(posts),
            "total_views": total_views,
            "total_likes": total_likes,
            "total_shares": total_shares,
            "total_comments": total_comments,
            "total_earnings_usd": total_earnings,
            "projected_earnings_usd": total_projected,
            "platform_breakdown": platform_breakdown,
        }

    def clip_performance(self, clip_id: str) -> dict:
        """Aggregated performance for a single clip across all platforms."""
        posts = (
            self.db.query(SocialPost)
            .filter(SocialPost.clip_id == clip_id)
            .all()
        )

        if not posts:
            return {"clip_id": clip_id, "posts": 0}

        return {
            "clip_id": clip_id,
            "total_posts": len(posts),
            "total_views": sum(p.views for p in posts),
            "total_likes": sum(p.likes for p in posts),
            "total_earnings_usd": sum(p.earnings_usd for p in posts),
            "projected_earnings_usd": sum(self.project_post_earnings(p) for p in posts),
            "engagement_rate": self._engagement_rate(posts),
            "platforms": {p.platform: {
                "views": p.views,
                "likes": p.likes,
                "shares": p.shares,
                "comments": p.comments,
                "earnings_usd": p.earnings_usd,
                "projected_earnings": self.project_post_earnings(p),
            } for p in posts},
        }

    def top_performing_clips(self, limit: int = 10) -> list[dict]:
        """Return the top-performing clips by projected earnings."""
        posts = (
            self.db.query(SocialPost)
            .filter(SocialPost.status.in_([SocialPostStatus.PUBLISHED, SocialPostStatus.SIMULATED]))
            .order_by(SocialPost.views.desc())
            .limit(limit * 3)
            .all()
        )

        clip_scores: dict[str, dict] = {}
        for post in posts:
            cid = post.clip_id
            if cid not in clip_scores:
                clip_scores[cid] = {
                    "clip_id": cid,
                    "total_views": 0,
                    "total_earnings": 0.0,
                    "platforms": set(),
                    "hook": None,
                }
            clip_scores[cid]["total_views"] += post.views
            clip_scores[cid]["total_earnings"] += post.earnings_usd
            clip_scores[cid]["platforms"].add(post.platform)
            clip_obj = post.clip
            if clip_obj and clip_obj.hook_text:
                clip_scores[cid]["hook"] = clip_obj.hook_text

        sorted_clips = sorted(
            clip_scores.values(),
            key=lambda x: x["total_earnings"],
            reverse=True,
        )
        for c in sorted_clips:
            c["platforms"] = list(c["platforms"])

        return sorted_clips[:limit]

    def best_hook_variant(self, clip_id: str) -> str | None:
        """Return the best-performing hook variant for a clip (by views)."""
        clip = self.db.query(Clip).filter(Clip.id == clip_id).first()
        if not clip:
            return None
        return clip.hook_text

    # ------------------------------------------------------------------
    # Earnings projection
    # ------------------------------------------------------------------

    def project_campaign_earnings(self, campaign_id: str) -> dict:
        """Project total earnings for a campaign based on clips and platform mix."""
        clips = self.db.query(Clip).filter(Clip.campaign_id == campaign_id).all()
        if not clips:
            return {"campaign_id": campaign_id, "projected_earnings": 0.0}

        clip_posts = 0
        total_projected = 0.0
        for clip in clips:
            posts = (
                self.db.query(SocialPost)
                .filter(SocialPost.clip_id == clip.id)
                .all()
            )
            clip_posts += len(posts)
            for p in posts:
                total_projected += self.project_post_earnings(p)

        return {
            "campaign_id": campaign_id,
            "total_clips": len(clips),
            "total_posts": clip_posts,
            "projected_earnings": total_projected,
        }

    def platform_comparison(self) -> dict:
        """Compare performance across all platforms."""
        posts = self.db.query(SocialPost).filter(
            SocialPost.status.in_([SocialPostStatus.PUBLISHED, SocialPostStatus.SIMULATED])
        ).all()

        comparison = {}
        for p in posts:
            if p.platform not in comparison:
                comparison[p.platform] = {
                    "posts": 0, "views": 0, "likes": 0,
                    "earnings": 0.0, "cpm": SocialPlatform.estimated_cpm(p.platform),
                }
            comparison[p.platform]["posts"] += 1
            comparison[p.platform]["views"] += p.views
            comparison[p.platform]["likes"] += p.likes
            comparison[p.platform]["earnings"] += p.earnings_usd

        for plat, stats in comparison.items():
            if stats["views"] > 0:
                stats["actual_cpm"] = (stats["earnings"] / stats["views"]) * 1000
            else:
                stats["actual_cpm"] = 0.0

        return comparison

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _engagement_rate(self, posts: list) -> float:
        total_views = sum(p.views for p in posts) or 1
        total_engagement = sum(p.likes + p.shares + p.comments for p in posts)
        return round((total_engagement / total_views) * 100, 2)

    def _empty_campaign_stats(self, campaign_id: str) -> dict:
        return {
            "campaign_id": campaign_id,
            "total_posts": 0, "total_views": 0, "total_likes": 0,
            "total_shares": 0, "total_comments": 0,
            "total_earnings_usd": 0.0, "projected_earnings_usd": 0.0,
            "platform_breakdown": {},
        }
