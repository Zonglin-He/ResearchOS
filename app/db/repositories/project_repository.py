from abc import ABC, abstractmethod
from app.schemas.project import Project

class ProjectRepository(ABC):
    @abstractmethod
    def create(self, project: Project) -> Project:
        ...

    @abstractmethod
    def get_by_id(self, project_id: str) -> Project | None:
        ...

    @abstractmethod
    def list_all(self) -> list[Project]:
        ...

    @abstractmethod
    def delete(self, project_id: str) -> None:
        ...
