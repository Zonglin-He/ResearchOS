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


class RunManifestRead(RunManifestCreate):
    start_time: datetime
    end_time: datetime | None = None
    status: str
    metrics: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[str] = Field(default_factory=list)
    dispatch_routing: ResolvedDispatchModel | None = None
