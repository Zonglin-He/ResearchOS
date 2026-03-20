from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class VerificationStatus(str, Enum):
    VERIFIED = "verified"
    INCOMPLETE = "incomplete"
    FAILED = "failed"
    NOT_CHECKED = "not_checked"


class VerificationCheckType(str, Enum):
    CLAIM_EVIDENCE = "claim_evidence"
    ARTIFACT_COMPLETENESS = "artifact_completeness"
    FREEZE_CONSISTENCY = "freeze_consistency"
    RUN_MANIFEST_SANITY = "run_manifest_sanity"


@dataclass
class VerificationRecord:
    verification_id: str
    subject_type: str
    subject_id: str
    check_type: VerificationCheckType
    status: VerificationStatus
    rationale: str
    evidence_refs: list[str] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class VerificationSummary:
    total_checks: int
    status_counts: dict[str, int] = field(default_factory=dict)
    check_type_counts: dict[str, int] = field(default_factory=dict)
    subject_type_counts: dict[str, int] = field(default_factory=dict)
