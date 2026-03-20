from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    project_id: str
    name: str
    description: str
    status: str = "active"


class ProjectRead(ProjectCreate):
    created_at: datetime


class TaskCreate(BaseModel):
    task_id: str
    project_id: str
    kind: str
    goal: str
    input_payload: dict[str, Any] = Field(default_factory=dict)
    owner: str
    assigned_agent: str | None = None
    parent_task_id: str | None = None


class TaskRead(TaskCreate):
    status: str
    created_at: datetime


class TaskStatusUpdate(BaseModel):
    status: str


class ClaimCreate(BaseModel):
    claim_id: str
    text: str
    claim_type: str
    risk_level: str = "medium"
    approved_by_human: bool = False


class ClaimRead(ClaimCreate):
    supported_by_runs: list[str] = Field(default_factory=list)
    supported_by_tables: list[str] = Field(default_factory=list)


class RunManifestCreate(BaseModel):
    run_id: str
    spec_id: str
    git_commit: str
    config_hash: str
    dataset_snapshot: str
    seed: int
    gpu: str


class RunManifestRead(RunManifestCreate):
    start_time: datetime
    end_time: datetime | None = None
    status: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)


class ApprovalCreate(BaseModel):
    approval_id: str
    project_id: str
    target_type: str
    target_id: str
    approved_by: str
    decision: str
    comment: str = ""


class ApprovalRead(ApprovalCreate):
    created_at: datetime
