from app.db.repositories.task_repository import TaskRepository
from app.schemas.task import Task, TaskStatus
from app.services.task_lifecycle import ensure_transition_allowed


class TaskService:
    def __init__(self, repository: TaskRepository) -> None:
        self.repository = repository

    def create_task(self, task: Task) -> Task:
        return self.repository.create(task)

    def get_task(self, task_id: str) -> Task | None:
        return self.repository.get_by_id(task_id)

    def list_tasks(self) -> list[Task]:
        return self.repository.list_all()

    def delete_task(self, task_id: str) -> None:
        self.repository.delete(task_id)

    def update_status(self, task_id: str, new_status: TaskStatus) -> Task:
        task = self.repository.get_by_id(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")

        ensure_transition_allowed(task.status, new_status)
        task.status = new_status
        return self.repository.update(task)

    def retry_task(self, task_id: str) -> Task:
        task = self.repository.get_by_id(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")

        if task.status not in {TaskStatus.FAILED, TaskStatus.BLOCKED}:
            raise ValueError(
                f"Cannot retry task {task_id} from status {task.status.value}"
            )

        task.status = TaskStatus.QUEUED
        task.assigned_agent = None
        return self.repository.update(task)

    def cancel_task(self, task_id: str) -> Task:
        return self.update_status(task_id, TaskStatus.CANCELLED)

    def attach_experiment_proposal(self, task_id: str, proposal_id: str) -> Task:
        task = self.repository.get_by_id(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        task.experiment_proposal_id = proposal_id
        return self.repository.update(task)

