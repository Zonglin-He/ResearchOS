from app.db.repositories.in_memory_project_repository import InMemoryProjectRepository
from app.schemas.project import Project
from app.services.project_service import ProjectService


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
