from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.schemas.run_manifest import RunManifest
from app.services.registry_store import append_jsonl, read_jsonl, to_record


class RunService:
    def __init__(self, registry_path: str | Path = "registry/runs.jsonl") -> None:
        self.registry_path = Path(registry_path)

    def register_run(self, manifest: RunManifest) -> RunManifest:
        append_jsonl(self.registry_path, to_record(manifest))
        return manifest

    def get_run(self, run_id: str) -> RunManifest | None:
        for run in self.list_runs():
            if run.run_id == run_id:
                return run
        return None

    def list_runs(self) -> list[RunManifest]:
        rows = read_jsonl(self.registry_path)
        return [
            RunManifest(
                run_id=row["run_id"],
                spec_id=row["spec_id"],
                git_commit=row["git_commit"],
                config_hash=row["config_hash"],
                dataset_snapshot=row["dataset_snapshot"],
                seed=row["seed"],
                gpu=row["gpu"],
                start_time=datetime.fromisoformat(row["start_time"]),
                end_time=datetime.fromisoformat(row["end_time"])
                if row.get("end_time")
                else None,
                status=row.get("status", "pending"),
                metrics=row.get("metrics", {}),
                artifacts=row.get("artifacts", []),
            )
            for row in rows
        ]
