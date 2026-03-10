from app.db.repositories.project_repository import ProjectRepository
from app.schemas.project import Project

class InMemoryProjectRepository(ProjectRepository):
    def __init__(self):
        self._projects: dict[str, Project] = {}

    def create(self, project: Project) -> Project:
        self._projects[project.project_id] = project
        return project

    def get_by_id(self, project_id: str) -> Project | None:
        return self._projects.get(project_id)

    def list_all(self) -> list[Project]:
        return list(self._projects.values())

    def delete(self, project_id: str) -> None:
        self._projects.pop(project_id, None)

