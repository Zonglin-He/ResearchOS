from app.db.repositories.task_repository import TaskRepository
from app.schemas.task import Task


class InMemoryTaskRepository(TaskRepository):
    def __init__(self) -> None:
        self._tasks: dict[str, Task] = {}

    def create(self, task: Task) -> Task:
        self._tasks[task.task_id] = task
        return task

    def update(self, task: Task) -> Task:
        self._tasks[task.task_id] = task
        return task

    def get_by_id(self, task_id: str) -> Task | None:
        return self._tasks.get(task_id)

    def list_all(self) -> list[Task]:
        return list(self._tasks.values())

    def delete(self, task_id: str) -> None:
        self._tasks.pop(task_id, None)
