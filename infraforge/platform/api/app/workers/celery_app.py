from celery import Celery
from app.config import get_settings

settings = get_settings()

celery_app = Celery(
    "infraforge",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "sweep-stale-runs": {
            "task": "app.workers.tasks.sweep_stale_runs",
            "schedule": 60.0,  # every 60 seconds
        },
        "update-lab-stats": {
            "task": "app.workers.tasks.update_lab_stats",
            "schedule": 3600.0,  # every hour
        },
    },
)
