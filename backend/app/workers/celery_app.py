"""
Celery application configuration for EvalForge AI.

The Celery app handles async eval execution via Redis broker.
Tasks are executed by the worker pool; API enqueues tasks and polls status.
"""

from __future__ import annotations

import logging

from celery import Celery

from app.core.config import get_settings

logger = logging.getLogger("evalforge.celery")

settings = get_settings()

celery_app = Celery(
    "evalforge",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,  # Re-deliver on worker crash
    worker_prefetch_multiplier=1,  # One task per worker at a time (eval tasks are heavy)
    task_soft_time_limit=120,  # 2 min soft limit per task
    task_time_limit=180,  # 3 min hard limit
    task_default_retry_delay=10,  # 10s between retries
    task_max_retries=2,  # Max 2 retries per task
    result_expires=3600,  # Keep results for 1 hour
    broker_connection_retry_on_startup=True,
)

logger.info(
    "Celery configured: broker=%s, concurrency settings loaded",
    settings.redis_url,
)
