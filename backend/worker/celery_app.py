import os
from celery import Celery

broker_url = os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/0")
result_backend = os.getenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/0")

celery_app = Celery(
    "livecaptions",
    broker=broker_url,
    backend=result_backend,
    include=["backend.worker.tasks"]
)

# Optional: Configuration optimizations
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_prefetch_multiplier=1, # Important for long running tasks
    task_acks_late=True, # Ensure task is not lost if worker crashes
)
