from pathlib import Path

from app.routing.models import DispatchProfile, ProviderSpec, ResolvedDispatch
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
        dispatch_profile=DispatchProfile(
            provider=ProviderSpec(provider_name="claude", model="sonnet"),
        ),
    )

    repository.create(project)
    result = repository.get_by_id("p1")

    assert result is not None
    assert result.project_id == "p1"
    assert result.name == "ResearchOS"
    assert result.dispatch_profile is not None
    assert result.dispatch_profile.provider is not None
    assert result.dispatch_profile.provider.provider_name == "claude"


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
        dispatch_profile=DispatchProfile(
            provider=ProviderSpec(provider_name="codex", model="gpt-5.4"),
        ),
    )

    task_repository.create(task)
    task.status = TaskStatus.RUNNING
    task.last_run_routing = ResolvedDispatch(
        provider_name="codex",
        model="gpt-5.4",
        max_steps=12,
        sources={"provider_name": "task_override", "model": "task_override", "max_steps": "system_default"},
    )
    task_repository.update(task)
    result = task_repository.get_by_id("t1")

    assert result is not None
    assert result.task_id == "t1"
    assert result.project_id == "p1"
    assert result.input_payload["paper_id"] == "1234.5678"
    assert result.status == TaskStatus.RUNNING
    assert result.dispatch_profile is not None
    assert result.dispatch_profile.provider is not None
    assert result.dispatch_profile.provider.provider_name == "codex"
    assert result.last_run_routing is not None
    assert result.last_run_routing.provider_name == "codex"
