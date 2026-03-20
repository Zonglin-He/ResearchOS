from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.schemas.artifact_annotation import ArtifactAnnotation, ArtifactAnnotationStatus
from app.services.registry_store import append_jsonl, read_jsonl, to_record


class ArtifactAnnotationService:
    def __init__(self, registry_path: str | Path = "registry/artifact_annotations.jsonl") -> None:
        self.registry_path = Path(registry_path).expanduser().resolve()

    def record_annotation(self, annotation: ArtifactAnnotation) -> ArtifactAnnotation:
        append_jsonl(self.registry_path, to_record(annotation))
        return annotation

    def list_annotations(self, artifact_id: str | None = None) -> list[ArtifactAnnotation]:
        annotations = self._read_annotations()
        if artifact_id is None:
            return annotations
        return [annotation for annotation in annotations if annotation.artifact_id == artifact_id]

    def _read_annotations(self) -> list[ArtifactAnnotation]:
        rows = read_jsonl(self.registry_path)
        return [
            ArtifactAnnotation(
                annotation_id=row["annotation_id"],
                artifact_id=row["artifact_id"],
                operator=row["operator"],
                status=ArtifactAnnotationStatus(
                    row.get("status", ArtifactAnnotationStatus.PENDING_REVIEW.value)
                ),
                review_tags=row.get("review_tags", []),
                note=row.get("note", ""),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]
