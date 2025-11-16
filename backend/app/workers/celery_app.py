from celery import Celery

celery_app = Celery(
    "worker",
    broker='redis://redis:6379/0',
    backend='redis://redis:6379/1',
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_track_started=True,
)
