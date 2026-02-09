from celery import Celery
from app.core.config import settings


def _pick_first(*values):
    for value in values:
        if value:
            return value
    return None


broker_url = _pick_first(
    settings.CELERY_BROKER_URL,
    settings.REDIS_URL,
)

result_backend = _pick_first(
    settings.CELERY_RESULT_BACKEND,
    settings.REDIS_URL,
)

if not broker_url or not result_backend:
    raise RuntimeError(
        "Celery broker/result backend not configured. "
        "Set CELERY_BROKER_URL and CELERY_RESULT_BACKEND."
    )

celery_app = Celery(
    "worker",
    broker=broker_url,
    backend=result_backend,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    # Task Tracking
    task_track_started=True,

    # Serialization (JSON is safer for production)
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Performance Optimizations
    worker_prefetch_multiplier=4,  # Tasks prefetched per worker
    task_acks_late=True,  # Acknowledge after completion (prevents task loss)
    task_reject_on_worker_lost=True,

    # Result Backend
    result_expires=3600,  # Results expire after 1 hour
    result_compression="gzip",

    # Timeouts (should match task definitions)
    task_soft_time_limit=900,  # 15 minutes
    task_time_limit=1000,  # 16+ minutes

    # Retries
    task_default_retry_delay=60,
    task_max_retries=5,

    # Avoid Celery 6 deprecation warning
    broker_connection_retry_on_startup=True,
)
