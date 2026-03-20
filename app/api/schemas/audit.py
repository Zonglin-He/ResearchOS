from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class AuditEntryRead(BaseModel):
    entry_id: str
    subject_type: str
    subject_id: str
    category: str
    status: str
    rationale: str
    evidence_refs: list[str] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    related_run_ids: list[str] = Field(default_factory=list)
    related_claim_ids: list[str] = Field(default_factory=list)
    created_at: datetime


class AuditReportRead(BaseModel):
    report_type: str
    status: str
    findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    entries: list[AuditEntryRead] = Field(default_factory=list)


class AuditSummaryRead(BaseModel):
    total_reports: int
    total_entries: int
    report_status_counts: dict[str, int] = Field(default_factory=dict)
    entry_status_counts: dict[str, int] = Field(default_factory=dict)
    findings: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
