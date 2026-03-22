from app.core.enums import Stage
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

    def save_project(self, project: Project) -> Project:
        return self.repository.create(project)

    def update_stage(self, project_id: str, stage: Stage) -> Project:
        project = self.get_project(project_id)
        if project is None:
            raise KeyError(f"Project not found: {project_id}")
        project.stage = stage
        return self.repository.create(project)

    def delete_project(self, project_id: str) -> None:
        self.repository.delete(project_id)
