from __future__ import annotations

from pydantic import BaseModel, Field


class ProvenanceEvidenceRefRead(BaseModel):
    ref_type: str
    ref_id: str
    raw_ref: str


class AuditSubjectRefRead(BaseModel):
    subject_type: str
    subject_id: str
    category: str
    status: str
    rationale: str
    entry_id: str | None = None
    evidence_refs: list[ProvenanceEvidenceRefRead] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)


class VerificationLinkRead(BaseModel):
    verification_id: str
    subject_type: str
    subject_id: str
    check_type: str
    status: str
    rationale: str
    evidence_refs: list[ProvenanceEvidenceRefRead] = Field(default_factory=list)
    artifact_ids: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)


class ClaimSupportRefRead(BaseModel):
    claim_id: str
    support_kind: str
    support_value: str


class RunEvidenceRefRead(BaseModel):
    run_id: str
    spec_id: str
    status: str
    artifact_ids: list[str] = Field(default_factory=list)


class ArtifactProvenanceRead(BaseModel):
    artifact_id: str
    run_id: str
    resolved_path: str
    workspace_relative_path: str | None = None
    exists_on_disk: bool
    run_evidence: RunEvidenceRefRead | None = None
    verification_links: list[VerificationLinkRead] = Field(default_factory=list)
    audit_subject_refs: list[AuditSubjectRefRead] = Field(default_factory=list)
    claim_support_refs: list[ClaimSupportRefRead] = Field(default_factory=list)
    freeze_subject_refs: list[AuditSubjectRefRead] = Field(default_factory=list)
