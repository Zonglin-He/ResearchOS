from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class RunEvent:
    project_id: str
    event_type: str
    message: str
    payload: dict[str, Any] = field(default_factory=dict)
    task_id: str | None = None
    run_id: str | None = None
    event_id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ConversationMessage:
    project_id: str
    thread_id: str
    role: str
    content: str
    gap_id: str | None = None
    human_select_task_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    message_id: int | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
