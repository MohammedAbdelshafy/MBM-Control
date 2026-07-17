"""
Monetization Celery tasks — 24/7 revenue assurance monitoring.
"""
from app.core.celery_app import celery_app
from app.core.logging_config import get_logger
from app.workers.campaign_tasks import JobTrackedTask

logger = get_logger("workers.monetization")


@celery_app.task(
    name="app.workers.monetization_tasks.run_monetization_check",
    base=JobTrackedTask,
    bind=True,
    queue="health",
    soft_time_limit=120,
)
def run_monetization_check(self):
    from app.core.database import SyncSessionLocal
    from app.agents.monetization_agent import MonetizationAgent

    db = SyncSessionLocal()
    try:
        agent = MonetizationAgent(db=db)
        result = agent._safe_run()
        if not result.success:
            raise ValueError(result.error or "Monetization check failed")
        db.commit()
        return result.data
    except Exception as exc:
        db.rollback()
        logger.error(f"Monetization check failed: {exc}")
        return {"error": str(exc)}
    finally:
        db.close()
