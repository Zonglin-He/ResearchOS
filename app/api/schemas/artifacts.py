from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.api.schemas.artifact_annotations import ArtifactAnnotationRead
from app.api.schemas.audit import AuditEntryRead
from app.api.schemas.provenance import ArtifactProvenanceRead
from app.api.schemas.verifications import VerificationRead


class ArtifactRead(BaseModel):
    artifact_id: str
    run_id: str
    kind: str
    path: str
    hash: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class ArtifactDetailRead(ArtifactRead):
    resolved_path: str
    workspace_relative_path: str | None = None
    exists_on_disk: bool
    related_verifications: list[VerificationRead] = Field(default_factory=list)
    related_audit_entries: list[AuditEntryRead] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    provenance: ArtifactProvenanceRead
    annotations: list[ArtifactAnnotationRead] = Field(default_factory=list)
