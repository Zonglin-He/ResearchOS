from __future__ import annotations

from pathlib import Path

from app.schemas.artifact import ArtifactRecord
from app.services.registry_store import append_jsonl, read_jsonl, to_record


class ArtifactService:
    def __init__(self, registry_path: str | Path = "registry/artifacts.jsonl") -> None:
        self.registry_path = Path(registry_path).expanduser().resolve()

    def register_artifact(self, artifact: ArtifactRecord) -> ArtifactRecord:
        append_jsonl(self.registry_path, to_record(artifact))
        return artifact

    def list_artifacts(self) -> list[ArtifactRecord]:
        rows = read_jsonl(self.registry_path)
        return [
            ArtifactRecord(
                artifact_id=row["artifact_id"],
                run_id=row["run_id"],
                kind=row["kind"],
                path=row["path"],
                hash=row["hash"],
                metadata=row.get("metadata", {}),
            )
            for row in rows
        ]
