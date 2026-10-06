"""
Celery Application Factory.
Configured to use Redis as both the message broker and result backend.
Handles asynchronous background workloads like AI moderation webhook 
dispatching and cache invalidation.
"""
from celery import Celery
from app.core.config import settings

celery_app = Celery(
    "ngx_terminal_worker",
    broker=str(settings.REDIS_URL),
    backend=str(settings.REDIS_URL),
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Africa/Lagos",
    enable_utc=True,
    task_track_started=True,
    # Prevent worker from consuming all Droplet memory
    worker_max_memory_per_child=256_000,  # 256MB per worker process
)

# Auto-discover tasks in the workers module
celery_app.autodiscover_tasks(["app.workers"])