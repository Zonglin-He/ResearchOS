from __future__ import annotations

from fastapi import Request

from app.services.project_service import ProjectService
from app.services.task_service import TaskService


def get_project_service(request: Request) -> ProjectService:
    return request.app.state.project_service


def get_task_service(request: Request) -> TaskService:
    return request.app.state.task_service
