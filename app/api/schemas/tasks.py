from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.api.schemas.routing import DispatchProfileModel, ResolvedDispatchModel
from app.api.schemas.strategy import HandoffPacketRead, RetrievalEvidenceRead, StrategyTraceRead


class TaskCreate(BaseModel):
    task_id: str
    project_id: str
    kind: str
    goal: str
    input_payload: dict[str, Any] = Field(default_factory=dict)
    owner: str
    assigned_agent: str | None = None
    parent_task_id: str | None = None
    depends_on: list[str] = Field(default_factory=list)
    join_key: str | None = None
    fanout_group: str | None = None
    max_retries: int = 2
    dispatch_profile: DispatchProfileModel | None = None


class TaskRead(TaskCreate):
    status: str
    experiment_proposal_id: str | None = None
    last_run_routing: ResolvedDispatchModel | None = None
    retry_count: int
    last_error: str | None = None
    next_retry_at: datetime | None = None
    checkpoint_path: str | None = None
    latest_strategy_trace: StrategyTraceRead | None = None
    latest_retrieval_evidence: list[RetrievalEvidenceRead] = Field(default_factory=list)
    latest_handoff_packet: HandoffPacketRead | None = None
    created_at: datetime


class TaskStatusUpdate(BaseModel):
    status: str
