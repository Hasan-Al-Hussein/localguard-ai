"""Celery application configured for bounded, idempotent local execution."""

from __future__ import annotations

from celery import Celery  # type: ignore[import-untyped]
from localguard_api.config import get_settings

settings = get_settings()
celery_app = Celery(
    "localguard-worker",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=["localguard_worker.tasks"],
)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    enable_utc=True,
    timezone="UTC",
    worker_prefetch_multiplier=1,
    task_acks_late=True,
    task_acks_on_failure_or_timeout=False,
    task_reject_on_worker_lost=True,
    task_track_started=True,
    task_ignore_result=True,
    task_soft_time_limit=600,
    task_time_limit=660,
    broker_connection_retry_on_startup=True,
    broker_transport_options={"visibility_timeout": 900},
    result_expires=3600,
)
