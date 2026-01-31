from celery import Celery

celery_app = Celery(
    "worker",
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/1',
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    # Task Tracking
    task_track_started=True,
    
    # Serialization (JSON is safer for production)
    task_serializer='json',
    result_serializer='json',
    accept_content=['json'],
    
    # Performance Optimizations
    worker_prefetch_multiplier=4,  # Tasks prefetched per worker
    task_acks_late=True,  # Acknowledge after completion (prevents task loss)
    task_reject_on_worker_lost=True,
    
    # Result Backend
    result_expires=3600,  # Results expire after 1 hour
    result_compression='gzip',
    
    # Timeouts (should match task definitions)
    task_soft_time_limit=900,  # 15 minutes
    task_time_limit=1000,  # 16+ minutes
    
    # Retries
    task_default_retry_delay=60,
    task_max_retries=5,
)

