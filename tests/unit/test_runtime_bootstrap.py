from pathlib import Path

from app.bootstrap import build_runtime_services
from app.core.config import AppConfig
from app.schemas.project import Project
from app.schemas.task import Task


def test_runtime_bootstrap_uses_sqlite_when_database_url_is_empty(tmp_path: Path) -> None:
    config = AppConfig(db_path=str(tmp_path / "researchos.db"))
    services = build_runtime_services(config)

    services.project_service.create_project(
        Project(
            project_id="p1",
            name="ResearchOS",
            description="Bootstrap project",
            status="active",
        )
    )
    services.task_service.create_task(
        Task(
            task_id="t1",
            project_id="p1",
            kind="paper_ingest",
            goal="Ingest paper",
            input_payload={},
            owner="gabriel",
        )
    )

    assert services.project_service.get_project("p1") is not None
    assert services.task_service.get_task("t1") is not None
    assert services.tool_registry.get("filesystem").name == "filesystem"
    assert services.experiment_manager is not None
    assert services.lessons_service is not None
    assert services.verification_service is not None
    assert services.orchestrator is not None
