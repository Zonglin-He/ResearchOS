from app.db.repositories.in_memory_project_repository import InMemoryProjectRepository
from app.schemas.project import Project

def test_create_and_get_project_by_id():
    repository = InMemoryProjectRepository()
    project = Project(project_id="p1",
                      name="ResearchOS",
                      description="test project",
                      status="Active")
    repository.create(project)
    result = repository.get_by_id("p1")
    assert result is not None
    assert result.project_id == "p1"
    assert result.name == "ResearchOS"

    def test_delete_project_removes_it() -> None:
        repository = InMemoryProjectRepository()
        project = Project(project_id="p1",
                          name="ResearchOS",
                          description="test project",
                          status="Active")
        repository.create(project)
        repository.delete("p1")

        result = repository.get_by_id("p1")

        assert result is None