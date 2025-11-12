from celery import Celery
from backend.app.core.config import settings

celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER,
    backend=settings.CELERY_BACKEND,
    include=["backend.app.workers.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
)
