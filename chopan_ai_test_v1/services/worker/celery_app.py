from celery import Celery
import os
from config import config

# Load Celery configuration
celery_config = config.get("celery", {})

# Create Celery app
celery_app = Celery(
    "chopan_ai_worker",
    broker=celery_config.get("broker_url", "redis://localhost:6379/1"),
    backend=celery_config.get("result_backend", "redis://localhost:6379/2"),
    include=["services.worker.tasks"]
)

# Configure Celery
celery_app.conf.update(
    task_serializer=celery_config.get("task_serializer", "json"),
    result_serializer=celery_config.get("result_serializer", "json"),
    accept_content=celery_config.get("accept_content", ["json"]),
    timezone=celery_config.get("timezone", "UTC"),
    enable_utc=celery_config.get("enable_utc", True),
    task_routes=celery_config.get("task_routes", {}),
    task_annotations=celery_config.get("task_annotations", {}),
    worker_prefetch_multiplier=celery_config.get("worker_prefetch_multiplier", 1),
    task_acks_late=celery_config.get("task_acks_late", True),
    worker_max_tasks_per_child=celery_config.get("worker_max_tasks_per_child", 1000)
)

# Configure task queues
celery_app.conf.task_queues = {
    "content": {"exchange": "content", "routing_key": "content"},
    "email": {"exchange": "email", "routing_key": "email"},
    "social": {"exchange": "social", "routing_key": "social"},
    "prospect": {"exchange": "prospect", "routing_key": "prospect"},
    "snapshot": {"exchange": "snapshot", "routing_key": "snapshot"},
}

# Configure task routes
celery_app.conf.task_routes = {
    "content.*": {"queue": "content"},
    "email.*": {"queue": "email"},
    "social.*": {"queue": "social"},
    "prospect.*": {"queue": "prospect"},
    "snapshot.*": {"queue": "snapshot"},
}

# Configure beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "process-scheduled-content": {
        "task": "content.process_scheduled",
        "schedule": 60.0,  # Run every minute
    },
    "process-scheduled-social-posts": {
        "task": "social.process_scheduled",
        "schedule": 60.0,  # Run every minute
    },
    "process-scheduled-email-campaigns": {
        "task": "email.process_scheduled",
        "schedule": 60.0,  # Run every minute
    },
    "cleanup-old-snapshots": {
        "task": "snapshot.cleanup_old",
        "schedule": 3600.0,  # Run every hour
    },
}

if __name__ == "__main__":
    celery_app.start()