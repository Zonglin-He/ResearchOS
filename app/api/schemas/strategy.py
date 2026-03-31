from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RetrievalEvidenceRead(BaseModel):
    source_type: str
    source_id: str
    title: str
    snippet: str
    score: float
    why_selected: str


class StrategyTraceRead(BaseModel):
    task_id: str
    project_id: str
    should_retrieve: bool
    retrieval_targets: list[str] = Field(default_factory=list)
    should_call_tools: bool = False
    tool_candidates: list[str] = Field(default_factory=list)
    needs_human_checkpoint: bool = False
    reasoning_summary: str = ""
    created_at: datetime


class HandoffPacketRead(BaseModel):
    from_agent: str
    to_agent: str
    task_kind: str
    objective: str
    required_inputs: list[str] = Field(default_factory=list)
    attached_evidence_ids: list[str] = Field(default_factory=list)
    blocking_questions: list[str] = Field(default_factory=list)
    done_definition: str = ""


class MemoryRecordRead(BaseModel):
    record_id: str
    project_id: str
    bucket: str
    source_task_id: str | None = None
    summary: str
    confidence: float
    created_at: datetime
    expires_at: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
