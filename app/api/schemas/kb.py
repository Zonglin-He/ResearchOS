from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class KnowledgeRecordRead(BaseModel):
    record_id: str
    project_id: str
    title: str
    summary: str
    context_tags: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class KnowledgeBucketSummaryRead(BaseModel):
    bucket: str
    count: int
    latest_title: str = ""


class KnowledgeSummaryRead(BaseModel):
    buckets: list[KnowledgeBucketSummaryRead] = Field(default_factory=list)
