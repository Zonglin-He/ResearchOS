from app.db.repositories.project_repository import ProjectRepository
from app.schemas.project import Project

class ProjectService:
    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    def create_project(self, project: Project) -> Project:
        ...

    def get_project(self, project_id: str) -> Project | None:
        ...

    def list_projects(self) -> list[Project]:
        ...

    def delete_project(self, project_id: str) -> None:
        ...
