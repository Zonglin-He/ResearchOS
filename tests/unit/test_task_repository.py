from app.db.repositories.in_memory_task_repository import InMemoryTaskRepository
from app.schemas.task import Task


def test_create_and_get_task_by_id() -> None:
    repository = InMemoryTaskRepository()
    task = Task(
        task_id="t1",
        project_id="p1",
        kind="paper_ingest",
        goal="Ingest a paper",
        input_payload={},
        owner="gabriel",
    )

    repository.create(task)
    result = repository.get_by_id("t1")

    assert result is not None
    assert result.task_id == "t1"
    assert result.kind == "paper_ingest"


def test_delete_task_removes_it() -> None:
    repository = InMemoryTaskRepository()
    task = Task(
        task_id="t1",
        project_id="p1",
        kind="paper_ingest",
        goal="Ingest a paper",
        input_payload={},
        owner="gabriel",
    )

    repository.create(task)
    repository.delete("t1")

    result = repository.get_by_id("t1")

    assert result is None
