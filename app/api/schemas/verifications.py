from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class VerificationRead(BaseModel):
    verification_id: str
    subject_type: str
    subject_id: str
    check_type: str
    status: str
    rationale: str
    evidence_refs: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    created_at: datetime


class VerificationSummaryRead(BaseModel):
    total_checks: int
    status_counts: dict[str, int] = Field(default_factory=dict)
    check_type_counts: dict[str, int] = Field(default_factory=dict)
    subject_type_counts: dict[str, int] = Field(default_factory=dict)
