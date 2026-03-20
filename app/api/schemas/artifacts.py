from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ArtifactRead(BaseModel):
    artifact_id: str
    run_id: str
    kind: str
    path: str
    hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)
