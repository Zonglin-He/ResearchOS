from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ProvenanceEvidenceRef:
    ref_type: str
    ref_id: str
    raw_ref: str


@dataclass(frozen=True)
class AuditSubjectRef:
    subject_type: str
    subject_id: str
    category: str
    status: str
    rationale: str
    entry_id: str | None = None
    evidence_refs: list[ProvenanceEvidenceRef] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class VerificationLink:
    verification_id: str
    subject_type: str
    subject_id: str
    check_type: str
    status: str
    rationale: str
    evidence_refs: list[ProvenanceEvidenceRef] = field(default_factory=list)
    artifact_ids: list[str] = field(default_factory=list)
    missing_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ClaimSupportRef:
    claim_id: str
    support_kind: str
    support_value: str


@dataclass(frozen=True)
class RunEvidenceRef:
    run_id: str
    spec_id: str
    status: str
    artifact_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ArtifactProvenance:
    artifact_id: str
    run_id: str
    resolved_path: str
    workspace_relative_path: str | None
    exists_on_disk: bool
    run_evidence: RunEvidenceRef | None = None
    verification_links: list[VerificationLink] = field(default_factory=list)
    audit_subject_refs: list[AuditSubjectRef] = field(default_factory=list)
    claim_support_refs: list[ClaimSupportRef] = field(default_factory=list)
    freeze_subject_refs: list[AuditSubjectRef] = field(default_factory=list)
