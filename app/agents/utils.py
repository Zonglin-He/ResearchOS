from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.schemas.artifact import ArtifactRecord
from app.schemas.task import Task


def child_task_id(parent_task: Task, suffix: str) -> str:
    return f"{parent_task.task_id}:{suffix}"


def build_child_task(
    parent_task: Task,
    *,
    kind: str,
    goal: str,
    input_payload: dict[str, Any],
    assigned_agent: str | None = None,
) -> Task:
    return Task(
        task_id=child_task_id(parent_task, kind),
        project_id=parent_task.project_id,
        kind=kind,
        goal=goal,
        input_payload=input_payload,
        owner=parent_task.owner,
        assigned_agent=assigned_agent,
        parent_task_id=parent_task.task_id,
        dispatch_profile=parent_task.dispatch_profile,
    )


def write_artifact(
    *,
    run_id: str,
    artifact_id: str,
    kind: str,
    content: str,
    extension: str,
    metadata: dict[str, Any] | None = None,
) -> ArtifactRecord:
    path = Path("artifacts") / run_id / f"{artifact_id}.{extension.lstrip('.')}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
    return ArtifactRecord(
        artifact_id=artifact_id,
        run_id=run_id,
        kind=kind,
        path=str(path),
        hash=digest,
        metadata=metadata or {},
    )
