from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.artifact_annotation import ArtifactAnnotationStatus


class ArtifactAnnotationCreate(BaseModel):
    annotation_id: str
    operator: str
    status: ArtifactAnnotationStatus = ArtifactAnnotationStatus.PENDING_REVIEW
    review_tags: list[str] = Field(default_factory=list)
    note: str = ""


class ArtifactAnnotationRead(ArtifactAnnotationCreate):
    artifact_id: str
    created_at: datetime
