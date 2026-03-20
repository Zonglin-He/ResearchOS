from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class AuditEntry:
    entry_id: str
    subject_type: str
    subject_id: str
    category: str
    status: str
    rationale: str
    evidence_refs: list[str] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)
    related_run_ids: list[str] = field(default_factory=list)
    related_claim_ids: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class AuditReport:
    report_type: str
    status: str
    findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    entries: list[AuditEntry] = field(default_factory=list)


@dataclass
class AuditSummary:
    total_reports: int
    total_entries: int
    report_status_counts: dict[str, int] = field(default_factory=dict)
    entry_status_counts: dict[str, int] = field(default_factory=dict)
    findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
