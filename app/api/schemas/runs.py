from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.api.schemas.routing import ResolvedDispatchModel


class RunManifestCreate(BaseModel):
    run_id: str
    spec_id: str
    git_commit: str
    config_hash: str
    dataset_snapshot: str
    seed: int
    gpu: str
    status: str = "pending"
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)
    source_type: str = "internal"
    source_label: str | None = None
    source_metadata: dict[str, Any] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)


class RunManifestRead(RunManifestCreate):
    experiment_proposal_id: str | None = None
    experiment_branch: str | None = None
    start_time: datetime
    end_time: datetime | None = None
    dispatch_routing: ResolvedDispatchModel | None = None
