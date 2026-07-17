"""
Celery application factory.
All task queues, retry policies, and routing defined here.
Workers are started separately: `celery -A app.core.celery_app worker -Q <queue>`
"""
import ssl

from celery import Celery
from celery.signals import worker_ready, worker_shutdown
from kombu import Exchange, Queue

from app.core.config import get_settings

settings = get_settings()

# SSL config for rediss:// (Upstash and other TLS-only Redis providers)
_SSL_CONFIG = {"ssl_cert_reqs": ssl.CERT_NONE} if settings.redis_url.startswith("rediss://") else {}

# Queue definitions — each queue maps to a worker type
QUEUES = {
    "default": Queue("default", Exchange("default"), routing_key="default"),
    "campaigns": Queue("campaigns", Exchange("campaigns"), routing_key="campaigns"),
    "acquisition": Queue("acquisition", Exchange("acquisition"), routing_key="acquisition"),
    "analysis": Queue("analysis", Exchange("analysis"), routing_key="analysis"),
    "video": Queue("video", Exchange("video"), routing_key="video"),
    "delivery": Queue("delivery", Exchange("delivery"), routing_key="delivery"),
    "publish": Queue("publish", Exchange("publish"), routing_key="publish"),
    "health": Queue("health", Exchange("health"), routing_key="health"),
    "dlq": Queue("dlq", Exchange("dlq"), routing_key="dlq"),
}

celery_app = Celery(
    "clipping_factory",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.campaign_tasks",
        "app.workers.video_tasks",
        "app.workers.delivery_tasks",
        "app.workers.publish_tasks",
        "app.workers.health_tasks",
        "app.workers.ingestion_tasks",
        "app.workers.monetization_tasks",
        "app.workers.analytics_tasks",
    ],
)

celery_app.conf.update(
    # Queues
    task_queues=list(QUEUES.values()),
    task_default_queue="default",
    task_default_exchange="default",
    task_default_routing_key="default",

    # Serialization
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Timeouts
    task_soft_time_limit=3600,      # 1h soft limit — task gets SoftTimeLimitExceeded
    task_time_limit=4200,           # 70m hard kill
    result_expires=86400,           # Results kept 24h

    # Retries
    task_acks_late=True,            # Ack only after task completes (safe against worker crashes)
    task_reject_on_worker_lost=True,
    task_max_retries=3,

    # Concurrency
    worker_prefetch_multiplier=1,   # One task at a time per worker slot (fair for long tasks)
    worker_max_tasks_per_child=50,  # Recycle workers to avoid memory leaks

    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,

    # TLS/SSL for rediss:// (Upstash)
    broker_use_ssl=_SSL_CONFIG if _SSL_CONFIG else None,
    redis_backend_use_ssl=_SSL_CONFIG if _SSL_CONFIG else None,

    # Beat schedule (periodic tasks)
    beat_schedule={
        "scan-campaigns": {
            "task": "app.workers.campaign_tasks.scan_for_campaigns",
            "schedule": settings.clipping_scan_interval_seconds,
            "options": {"queue": "campaigns"},
        },
        "health-check": {
            "task": "app.workers.health_tasks.run_health_check",
            "schedule": 60,
            "options": {"queue": "health"},
        },
        "cleanup-temp-files": {
            "task": "app.workers.video_tasks.cleanup_temp_files",
            "schedule": 3600,
            "options": {"queue": "default"},
        },
        "requeue-stuck-clips": {
            "task": "app.workers.video_tasks.requeue_stuck_clips",
            "schedule": 600,  # Every 10 minutes
            "options": {"queue": "default"},
        },
        "ingest-lead-packs": {
            "task": "app.workers.ingestion_tasks.ingest_lead_packs",
            "schedule": 21600,
            "options": {"queue": "campaigns"},
        },
        "ingest-mbm-social-leads": {
            "task": "app.workers.ingestion_tasks.ingest_mbm_social_leads",
            "schedule": 43200,
            "options": {"queue": "campaigns"},
        },
        "monetization-check": {
            "task": "app.workers.monetization_tasks.run_monetization_check",
            "schedule": settings.monetization_check_interval_seconds,
            "options": {"queue": "health"},
        },
        "sync-analytics": {
            "task": "app.workers.analytics_tasks.sync_post_metrics",
            "schedule": 3600,
            "options": {"queue": "default"},
        },
    },

    # Task routing
    task_routes={
        "app.workers.campaign_tasks.*": {"queue": "campaigns"},
        "app.workers.video_tasks.acquire_content": {"queue": "acquisition"},
        "app.workers.video_tasks.analyze_content": {"queue": "analysis"},
        "app.workers.video_tasks.generate_clips": {"queue": "video"},
        "app.workers.video_tasks.edit_clip": {"queue": "video"},
        "app.workers.video_tasks.enhance_clip": {"queue": "video"},
        "app.workers.video_tasks.editor_quality_check": {"queue": "video"},
        "app.workers.delivery_tasks.*": {"queue": "delivery"},
        "app.workers.publish_tasks.*": {"queue": "publish"},
        "app.workers.health_tasks.*": {"queue": "health"},
        "app.workers.monetization_tasks.*": {"queue": "health"},
        "app.workers.ingestion_tasks.*": {"queue": "campaigns"},
        "app.workers.analytics_tasks.*": {"queue": "default"},
    },
)


@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    print(f"[Celery] Worker ready: {sender}")


@worker_shutdown.connect
def on_worker_shutdown(sender, **kwargs):
    print(f"[Celery] Worker shutdown: {sender}")


def get_celery() -> Celery:
    return celery_app
