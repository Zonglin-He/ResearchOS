from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ArtifactAnnotationStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    REVIEWED = "reviewed"
    FLAGGED = "flagged"


@dataclass
class ArtifactAnnotation:
    annotation_id: str
    artifact_id: str
    operator: str
    status: ArtifactAnnotationStatus = ArtifactAnnotationStatus.PENDING_REVIEW
    review_tags: list[str] = field(default_factory=list)
    note: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
