from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.routing.models import DispatchProfile, ResolvedDispatch


class TaskStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    BLOCKED = "blocked"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    task_id: str
    project_id: str
    kind: str
    goal: str
    input_payload: dict[str, Any]
    owner: str
    assigned_agent: str | None = None
    status: TaskStatus = TaskStatus.QUEUED
    parent_task_id: str | None = None
    experiment_proposal_id: str | None = None
    dispatch_profile: DispatchProfile | None = None
    last_run_routing: ResolvedDispatch | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
