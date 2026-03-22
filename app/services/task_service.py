from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.db.repositories.task_repository import TaskRepository
from app.schemas.activity import RunEvent
from app.schemas.task import Task, TaskStatus
from app.services.activity_service import ActivityService
from app.services.task_lifecycle import ensure_transition_allowed


class TaskService:
    def __init__(
        self,
        repository: TaskRepository,
        *,
        activity_service: ActivityService | None = None,
    ) -> None:
        self.repository = repository
        self.activity_service = activity_service

    def create_task(self, task: Task) -> Task:
        created = self.repository.create(task)
        self._record_event(
            created.project_id,
            event_type="task.created",
            message=f"Task created: {created.task_id}",
            task_id=created.task_id,
            payload={
                "kind": created.kind,
                "status": created.status.value,
                "depends_on": created.depends_on,
                "join_key": created.join_key,
                "fanout_group": created.fanout_group,
            },
        )
        return created

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

        previous_status = task.status
        ensure_transition_allowed(task.status, new_status)
        task.status = new_status
        updated = self.repository.update(task)
        self._record_event(
            updated.project_id,
            event_type="task.status_changed",
            message=f"Task {updated.task_id} moved from {previous_status.value} to {updated.status.value}",
            task_id=updated.task_id,
            payload={
                "previous_status": previous_status.value,
                "status": updated.status.value,
                "retry_count": updated.retry_count,
                "last_error": updated.last_error,
            },
        )
        return updated

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
        task.next_retry_at = None
        updated = self.repository.update(task)
        self._record_event(
            updated.project_id,
            event_type="task.retry_requested",
            message=f"Task queued for retry: {updated.task_id}",
            task_id=updated.task_id,
            payload={"retry_count": updated.retry_count, "status": updated.status.value},
        )
        return updated

    def cancel_task(self, task_id: str) -> Task:
        return self.update_status(task_id, TaskStatus.CANCELLED)

    def attach_experiment_proposal(self, task_id: str, proposal_id: str) -> Task:
        task = self.repository.get_by_id(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        task.experiment_proposal_id = proposal_id
        return self.repository.update(task)

    def list_runnable_tasks(self, *, project_id: str | None = None) -> list[Task]:
        tasks = self.repository.list_all()
        return [
            task
            for task in tasks
            if (project_id is None or task.project_id == project_id) and self.is_runnable(task)
        ]

    def dependencies_satisfied(self, task: Task) -> bool:
        if not task.depends_on:
            return True
        tasks_by_id = {item.task_id: item for item in self.repository.list_all()}
        return all(
            tasks_by_id.get(dependency_id) is not None
            and tasks_by_id[dependency_id].status == TaskStatus.SUCCEEDED
            for dependency_id in task.depends_on
        )

    def is_runnable(self, task: Task) -> bool:
        if task.status != TaskStatus.QUEUED:
            return False
        if not self.dependencies_satisfied(task):
            return False
        if task.next_retry_at is None:
            return True
        return task.next_retry_at <= datetime.now(timezone.utc)

    def mark_task_failed(self, task_id: str, *, error_detail: str, retryable: bool = True) -> Task:
        task = self.repository.get_by_id(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")

        task.last_error = error_detail.strip() or "Unknown task failure"
        task.retry_count += 1
        task.assigned_agent = None
        if retryable and task.retry_count <= task.max_retries:
            delay_seconds = min(300, 30 * (2 ** max(0, task.retry_count - 1)))
            if task.status != TaskStatus.QUEUED:
                task.status = TaskStatus.QUEUED
            task.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
            updated = self.repository.update(task)
            self._record_event(
                updated.project_id,
                event_type="task.retry_scheduled",
                message=f"Task {updated.task_id} scheduled to retry in {delay_seconds}s",
                task_id=updated.task_id,
                payload={
                    "retry_count": updated.retry_count,
                    "max_retries": updated.max_retries,
                    "next_retry_at": updated.next_retry_at.isoformat()
                    if updated.next_retry_at is not None
                    else None,
                    "error": updated.last_error,
                },
            )
            return updated

        if task.status != TaskStatus.FAILED:
            ensure_transition_allowed(task.status, TaskStatus.FAILED)
            task.status = TaskStatus.FAILED
        task.next_retry_at = None
        updated = self.repository.update(task)
        self._record_event(
            updated.project_id,
            event_type="task.failed",
            message=f"Task failed permanently: {updated.task_id}",
            task_id=updated.task_id,
            payload={
                "retry_count": updated.retry_count,
                "max_retries": updated.max_retries,
                "error": updated.last_error,
            },
        )
        return updated

    def save_task(self, task: Task) -> Task:
        return self.repository.update(task)

    def _record_event(
        self,
        project_id: str,
        *,
        event_type: str,
        message: str,
        task_id: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        if self.activity_service is None:
            return
        self.activity_service.record_event(
            RunEvent(
                project_id=project_id,
                task_id=task_id,
                event_type=event_type,
                message=message,
                payload=dict(payload or {}),
            )
        )
