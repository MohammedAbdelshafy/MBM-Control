"""
Analytics Celery tasks — performance tracking, platform comparison,
and periodic analytics sync.
"""
from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.workers.campaign_tasks import JobTrackedTask

logger = get_logger("workers.analytics")


@celery_app.task(
    name="app.workers.analytics_tasks.sync_post_metrics",
    base=JobTrackedTask,
    queue="default",
    soft_time_limit=120,
)
def sync_post_metrics(post_id: str | None = None):
    """
    Sync performance metrics for a specific post or all published posts.
    In production, this would call each platform's API to fetch view/like counts.
    In dev/demo, it simulates metrics.
    """
    from app.core.database import SyncSessionLocal
    from app.models.social_post import SocialPost, SocialPostStatus
    from app.services.analytics import AnalyticsService

    db = SyncSessionLocal()
    try:
        analytics = AnalyticsService(db=db)

        if post_id:
            posts = [db.query(SocialPost).filter(SocialPost.id == post_id).first()]
        else:
            posts = (
                db.query(SocialPost)
                .filter(SocialPost.status.in_([SocialPostStatus.PUBLISHED, SocialPostStatus.SIMULATED]))
                .all()
            )

        updated = 0
        for post in posts:
            if not post:
                continue
            # Simulated: generate realistic metrics
            import random
            views = random.randint(100, 50000)
            likes = int(views * random.uniform(0.02, 0.08))
            shares = int(views * random.uniform(0.005, 0.03))
            comments = int(views * random.uniform(0.002, 0.015))

            from app.models.social_post import SocialPlatform
            projected = (views / 1000) * SocialPlatform.estimated_cpm(post.platform)
            earnings = projected * random.uniform(0.3, 0.9)

            analytics.update_post_metrics(
                post_id=post.id,
                views=views,
                likes=likes,
                shares=shares,
                comments=comments,
                earnings_usd=round(earnings, 2),
            )
            updated += 1

        db.commit()
        logger.info(f"Synced metrics for {updated} posts")
        return {"updated": updated}
    except Exception as exc:
        db.rollback()
        logger.error(f"Analytics sync failed: {exc}")
        return {"error": str(exc)}
    finally:
        db.close()


@celery_app.task(
    name="app.workers.analytics_tasks.generate_campaign_report",
    base=JobTrackedTask,
    queue="default",
)
def generate_campaign_report(campaign_id: str):
    """Generate a performance report for a campaign."""
    from app.core.database import SyncSessionLocal
    from app.services.analytics import AnalyticsService

    db = SyncSessionLocal()
    try:
        analytics = AnalyticsService(db=db)
        report = analytics.campaign_performance(campaign_id)
        logger.info(
            f"Campaign {campaign_id[:8]} report: "
            f"{report['total_views']} views, ${report['total_earnings_usd']:.2f} earned"
        )
        return report
    except Exception as exc:
        logger.error(f"Campaign report failed: {exc}")
        return {"error": str(exc)}
    finally:
        db.close()
