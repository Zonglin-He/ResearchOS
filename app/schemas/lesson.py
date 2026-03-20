from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class LessonKind(str, Enum):
    LESSON = "lesson"
    ANTI_PATTERN = "anti_pattern"
    PLAYBOOK = "playbook"
    FAILURE_SIGNATURE = "failure_signature"


@dataclass
class LessonRecord:
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
    context_tags: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)
    source_task_id: str | None = None
    source_run_id: str | None = None
    source_claim_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
