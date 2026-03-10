from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal

TaskStatus = Literal[
    "queued",
    "running",
    "waiting_approval",
    "blocked",
    "succeeded",
    "failed",
    "cancelled",
    ]
@dataclass
class Task:
    task_id: str
    kind: str
    goal: str
    input_payload: dict[str, Any]
    owner: str
    assigned_agent: str | None = None
    status: TaskStatus = "queued"
    parent_task_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))