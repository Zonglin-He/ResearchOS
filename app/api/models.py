"""Compatibility re-export facade for legacy API model imports.

Deprecated:
    Prefer importing from ``app.api.schemas`` directly.
    This module remains in place for backward compatibility during the
    Iteration B compatibility window and should be removed only with an
    explicit migration note in a future breaking release.
"""

from app.api.schemas import (
    ArtifactDetailRead,
    ArtifactRead,
    AuditEntryRead,
    AuditReportRead,
    AuditSummaryRead,
    ApprovalCreate,
    ApprovalRead,
    ClaimCreate,
    ClaimRead,
    DispatchProfileModel,
    LessonCreate,
    LessonRead,
    ModelProfileModel,
    ProjectCreate,
    ProjectRead,
    ProviderSpecModel,
    ResolvedDispatchModel,
    RunManifestCreate,
    RunManifestRead,
    TaskCreate,
    TaskRead,
    TaskStatusUpdate,
    VerificationRead,
    VerificationSummaryRead,
)

__all__ = [
    "ArtifactDetailRead",
    "ArtifactRead",
    "AuditEntryRead",
    "AuditReportRead",
    "AuditSummaryRead",
    "ApprovalCreate",
    "ApprovalRead",
    "ClaimCreate",
    "ClaimRead",
    "DispatchProfileModel",
    "LessonCreate",
    "LessonRead",
    "ModelProfileModel",
    "ProjectCreate",
    "ProjectRead",
    "ProviderSpecModel",
    "ResolvedDispatchModel",
    "RunManifestCreate",
    "RunManifestRead",
    "TaskCreate",
    "TaskRead",
    "TaskStatusUpdate",
    "VerificationRead",
    "VerificationSummaryRead",
]
