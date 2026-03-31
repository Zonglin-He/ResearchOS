from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.routing.models import DispatchProfile, ResolvedDispatch
from app.schemas.strategy import HandoffPacket, RetrievalEvidence, StrategyTrace


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
    depends_on: list[str] = field(default_factory=list)
    join_key: str | None = None
    fanout_group: str | None = None
    experiment_proposal_id: str | None = None
    dispatch_profile: DispatchProfile | None = None
    last_run_routing: ResolvedDispatch | None = None
    retry_count: int = 0
    max_retries: int = 2
    last_error: str | None = None
    next_retry_at: datetime | None = None
    checkpoint_path: str | None = None
    latest_strategy_trace: StrategyTrace | None = None
    latest_retrieval_evidence: list[RetrievalEvidence] = field(default_factory=list)
    latest_handoff_packet: HandoffPacket | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
