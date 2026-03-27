from app.db.repositories.in_memory_project_repository import InMemoryProjectRepository
from app.core.enums import Stage
from app.schemas.project import Project
from app.services.project_service import ProjectService
from app.workflows.research_flow import FlowEvent, FlowStatus


def test_create_project_and_get_project() -> None:
    repository = InMemoryProjectRepository()
    service = ProjectService(repository)
    project = Project(
        project_id="p1",
        name="ResearchOS",
        description="test project",
        status="active",
    )

    service.create_project(project)
    result = service.get_project("p1")

    assert result is not None
    assert result.project_id == "p1"
    assert result.name == "ResearchOS"


def test_list_projects_returns_created_projects() -> None:
    repository = InMemoryProjectRepository()
    service = ProjectService(repository)

    project_1 = Project(
        project_id="p1",
        name="ResearchOS-1",
        description="test project 1",
        status="active",
    )
    project_2 = Project(
        project_id="p2",
        name="ResearchOS-2",
        description="test project 2",
        status="active",
    )

    service.create_project(project_1)
    service.create_project(project_2)

    result = service.list_projects()

    assert len(result) == 2
    assert result[0].project_id == "p1"
    assert result[1].project_id == "p2"


def test_project_service_initializes_and_transitions_flow_snapshot() -> None:
    repository = InMemoryProjectRepository()
    service = ProjectService(repository)
    project = service.create_project(
        Project(
            project_id="p3",
            name="ResearchOS Flow",
            description="typed flow test",
            status="active",
        )
    )

    snapshot = service.get_flow_snapshot(project.project_id)
    assert snapshot.stage == Stage.NEW_TOPIC
    assert snapshot.status == FlowStatus.PENDING

    service.transition_flow(
        project.project_id,
        event=FlowEvent.START,
        stage=Stage.INGEST_PAPERS,
        task_id="task-ingest",
        note="dispatch started",
    )
    running = service.get_flow_snapshot(project.project_id)
    assert running.stage == Stage.INGEST_PAPERS
    assert running.status == FlowStatus.RUNNING
    assert running.active_task_id == "task-ingest"

    service.transition_flow(
        project.project_id,
        event=FlowEvent.SUCCEED,
        stage=Stage.INGEST_PAPERS,
        task_id="task-ingest",
        note="dispatch completed",
    )
    advanced = service.get_flow_snapshot(project.project_id)
    assert advanced.stage == Stage.MAP_GAPS
    assert advanced.status == FlowStatus.PENDING
