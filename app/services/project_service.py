from app.db.repositories.project_repository import ProjectRepository
from app.schemas.project import Project

class ProjectService:
    def __init__(self, repository: ProjectRepository):
        self.repository = repository

    def create_project(self, project: Project) -> Project:
        return self.repository.create(project)

    def get_project(self, project_id: str) -> Project | None:
        return self.repository.get_by_id(project_id)

    def list_projects(self) -> list[Project]:
        return self.repository.list_all()

    def delete_project(self, project_id: str) -> None:
        self.repository.delete(project_id)
