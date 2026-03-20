"""Compatibility re-export facade for legacy API model imports.

Deprecated:
    Prefer importing from ``app.api.schemas`` directly.
    This module remains in place for backward compatibility during the
    Iteration B/C compatibility window and should be removed only with an
    explicit migration note in a future breaking release.

    New API schema additions should prefer canonical imports and should not
    expand this facade unless a compatibility requirement is explicitly
    justified.
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
