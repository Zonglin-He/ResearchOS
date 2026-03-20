from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.api.schemas.routing import DispatchProfileModel, ResolvedDispatchModel


class TaskCreate(BaseModel):
    task_id: str
    project_id: str
    kind: str
    goal: str
    input_payload: dict[str, Any] = Field(default_factory=dict)
    owner: str
    assigned_agent: str | None = None
    parent_task_id: str | None = None
    dispatch_profile: DispatchProfileModel | None = None


class TaskRead(TaskCreate):
    status: str
    last_run_routing: ResolvedDispatchModel | None = None
    created_at: datetime


class TaskStatusUpdate(BaseModel):
    status: str
