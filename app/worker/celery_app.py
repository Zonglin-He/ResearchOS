from __future__ import annotations

import os

from celery import Celery


broker_url = os.getenv("RESEARCHOS_REDIS_URL", "redis://localhost:6379/0")
result_backend = os.getenv("RESEARCHOS_CELERY_BACKEND", broker_url)

celery_app = Celery("researchos", broker=broker_url, backend=result_backend)
celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)
celery_app.autodiscover_tasks(["app.worker"])
