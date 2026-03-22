from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.lesson import LessonKind


class LessonCreate(BaseModel):
    lesson_id: str
    lesson_kind: LessonKind
    title: str
    summary: str
    rationale: str = ""
    recommended_action: str = ""
    task_kind: str | None = None
    agent_name: str | None = None
    tool_name: str | None = None
    provider_name: str | None = None
    model_name: str | None = None
    failure_type: str | None = None
    repository_ref: str | None = None
    dataset_ref: str | None = None
    context_tags: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    source_task_id: str | None = None
    source_run_id: str | None = None
    source_claim_id: str | None = None
    expires_at: datetime | None = None
    hit_count: int = 0
    last_hit_at: datetime | None = None
    is_valid: bool = True


class LessonRead(LessonCreate):
    created_at: datetime
