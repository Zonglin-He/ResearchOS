from pathlib import Path

from app.db.repositories.sqlite_project_repository import SQLiteProjectRepository
from app.db.repositories.sqlite_task_repository import SQLiteTaskRepository
from app.db.sqlite import SQLiteDatabase
from app.schemas.project import Project
from app.schemas.task import Task, TaskStatus


def test_sqlite_project_repository_roundtrip(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "researchos.db")
    database.initialize()
    repository = SQLiteProjectRepository(database)
    project = Project(
        project_id="p1",
        name="ResearchOS",
        description="SQLite-backed project",
        status="active",
    )

    repository.create(project)
    result = repository.get_by_id("p1")

    assert result is not None
    assert result.project_id == "p1"
    assert result.name == "ResearchOS"


def test_sqlite_task_repository_roundtrip(tmp_path: Path) -> None:
    database = SQLiteDatabase(tmp_path / "researchos.db")
    database.initialize()
    project_repository = SQLiteProjectRepository(database)
    task_repository = SQLiteTaskRepository(database)
    project_repository.create(
        Project(
            project_id="p1",
            name="ResearchOS",
            description="SQLite-backed project",
            status="active",
        )
    )
    task = Task(
        task_id="t1",
        project_id="p1",
        kind="paper_ingest",
        goal="Ingest a paper",
        input_payload={"paper_id": "1234.5678"},
        owner="gabriel",
    )

    task_repository.create(task)
    task.status = TaskStatus.RUNNING
    task_repository.update(task)
    result = task_repository.get_by_id("t1")

    assert result is not None
    assert result.task_id == "t1"
    assert result.project_id == "p1"
    assert result.input_payload["paper_id"] == "1234.5678"
    assert result.status == TaskStatus.RUNNING
