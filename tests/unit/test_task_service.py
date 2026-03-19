from app.db.repositories.in_memory_task_repository import InMemoryTaskRepository
from app.schemas.task import Task, TaskStatus
from app.services.task_service import TaskService


def test_create_task_and_get_task() -> None:
    repository = InMemoryTaskRepository()
    service = TaskService(repository)
    task = Task(
        task_id="t1",
        kind="paper_ingest",
        goal="Ingest a paper",
        input_payload={},
        owner="gabriel",
    )

    service.create_task(task)
    result = service.get_task("t1")

    assert result is not None
    assert result.task_id == "t1"
    assert result.kind == "paper_ingest"


def test_list_tasks_returns_created_tasks() -> None:
    repository = InMemoryTaskRepository()
    service = TaskService(repository)

    task_1 = Task(
        task_id="t1",
        kind="paper_ingest",
        goal="Ingest a paper",
        input_payload={},
        owner="gabriel",
    )
    task_2 = Task(
        task_id="t2",
        kind="build_cards",
        goal="Build paper cards",
        input_payload={},
        owner="gabriel",
    )

    service.create_task(task_1)
    service.create_task(task_2)

    result = service.list_tasks()

    assert len(result) == 2
    assert result[0].task_id == "t1"
    assert result[1].task_id == "t2"


def test_update_status_changes_task_status_when_transition_is_allowed() -> None:
    repository = InMemoryTaskRepository()
    service = TaskService(repository)
    task = Task(
        task_id="t1",
        kind="paper_ingest",
        goal="Ingest a paper",
        input_payload={},
        owner="gabriel",
    )

    service.create_task(task)
    result = service.update_status("t1", TaskStatus.RUNNING)

    assert result.status == TaskStatus.RUNNING
    assert service.get_task("t1") is not None
    assert service.get_task("t1").status == TaskStatus.RUNNING


def test_update_status_raises_value_error_for_illegal_transition() -> None:
    repository = InMemoryTaskRepository()
    service = TaskService(repository)
    task = Task(
        task_id="t1",
        kind="paper_ingest",
        goal="Ingest a paper",
        input_payload={},
        owner="gabriel",
    )

    service.create_task(task)

    try:
        service.update_status("t1", TaskStatus.SUCCEEDED)
        assert False, "Expected ValueError for illegal transition"
    except ValueError:
        pass
