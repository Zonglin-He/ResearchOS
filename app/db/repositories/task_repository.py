from abc import ABC, abstractmethod

from app.schemas.task import Task


class TaskRepository(ABC):
    @abstractmethod
    def create(self, task: Task) -> Task:
        ...

    @abstractmethod
    def update(self, task: Task) -> Task:
        ...

    @abstractmethod
    def get_by_id(self, task_id: str) -> Task | None:
        ...

    @abstractmethod
    def list_all(self) -> list[Task]:
        ...

    @abstractmethod
    def delete(self, task_id: str) -> None:
        ...
