from pathlib import Path

from app.schemas.task import Task
from app.schemas.strategy import RetrievalEvidence
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


def test_checkpoint_service_serializes_strategy_payloads(tmp_path) -> None:
    service = CheckpointService(tmp_path / "checkpoints")
    task = Task(
        task_id="task-with-evidence",
        project_id="p1",
        kind="paper_ingest",
        goal="persist retrieval evidence",
        input_payload={},
        owner="tester",
    )

    saved_path = service.save(
        task=task,
        stage="dispatch_succeeded",
        payload={
            "retrieval_evidence": (
                RetrievalEvidence(
                    source_type="paper_card",
                    source_id="paper-1",
                    title="Proof paper",
                    snippet="Matched on retrieval payload serialization.",
                    score=0.92,
                    why_selected="Highest lexical and recency score.",
                ),
            )
        },
    )

    assert Path(saved_path).exists()
    loaded = service.load(task.task_id)
    assert loaded is not None
    evidence = loaded["payload"]["retrieval_evidence"]
    assert isinstance(evidence, list)
    assert evidence[0]["source_id"] == "paper-1"
