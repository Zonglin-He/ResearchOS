from pathlib import Path

from app.schemas.task import Task
from app.services.checkpoint_service import CheckpointService


def test_checkpoint_service_sanitizes_windows_unsafe_task_ids(tmp_path) -> None:
    service = CheckpointService(tmp_path / "checkpoints")
    task = Task(
        task_id="project:branch_plan:branch-01",
        project_id="p1",
        kind="branch_plan",
        goal="checkpoint sanitization",
        input_payload={},
        owner="tester",
    )

    saved_path = service.save(task=task, stage="dispatch_started", payload={"ok": True})

    assert ":" not in Path(saved_path).name
    loaded = service.load(task.task_id)
    assert loaded is not None
    assert loaded["task_id"] == task.task_id
    assert loaded["payload"]["ok"] is True
