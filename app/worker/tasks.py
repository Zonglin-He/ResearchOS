from __future__ import annotations

import asyncio

from app.bootstrap import build_runtime_services
from app.core.config import load_config
from app.schemas.task import TaskStatus
from app.worker.celery_app import celery_app


@celery_app.task(name="researchos.ping")
def ping() -> dict[str, str]:
    return {"status": "ok"}


@celery_app.task(name="researchos.advance_task")
def advance_task(task_id: str, new_status: str) -> dict[str, str]:
    services = build_runtime_services(load_config())
    task = services.task_service.update_status(task_id, TaskStatus(new_status))
    return {"task_id": task.task_id, "status": task.status.value}


@celery_app.task(name="researchos.dispatch_task")
def dispatch_task(task_id: str) -> dict[str, str]:
    services = build_runtime_services(load_config())
    dispatch = asyncio.run(services.orchestrator.dispatch(task_id))
    return {
        "task_id": dispatch.task.task_id,
        "status": dispatch.task.status.value,
        "result_status": dispatch.result.status,
    }
