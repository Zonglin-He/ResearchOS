from __future__ import annotations

from app.db.models import TaskModel
from app.schemas.task import Task, TaskStatus


class SATaskRepository:
    def __init__(self, session_factory) -> None:
        self.session_factory = session_factory

    def create(self, task: Task) -> Task:
        with self.session_factory() as session:
            session.merge(self._to_model(task))
            session.commit()
        return task

    def update(self, task: Task) -> Task:
        with self.session_factory() as session:
            session.merge(self._to_model(task))
            session.commit()
        return task

    def get_by_id(self, task_id: str) -> Task | None:
        with self.session_factory() as session:
            model = session.get(TaskModel, task_id)
            if model is None:
                return None
            return self._to_schema(model)

    def list_all(self) -> list[Task]:
        with self.session_factory() as session:
            models = session.query(TaskModel).order_by(TaskModel.created_at).all()
        return [self._to_schema(model) for model in models]

    def delete(self, task_id: str) -> None:
        with self.session_factory() as session:
            model = session.get(TaskModel, task_id)
            if model is not None:
                session.delete(model)
                session.commit()

    @staticmethod
    def _to_model(task: Task) -> TaskModel:
        return TaskModel(
            task_id=task.task_id,
            project_id=task.project_id,
            kind=task.kind,
            goal=task.goal,
            input_payload=task.input_payload,
            owner=task.owner,
            assigned_agent=task.assigned_agent,
            status=task.status.value,
            parent_task_id=task.parent_task_id,
            created_at=task.created_at,
        )

    @staticmethod
    def _to_schema(model: TaskModel) -> Task:
        return Task(
            task_id=model.task_id,
            project_id=model.project_id,
            kind=model.kind,
            goal=model.goal,
            input_payload=model.input_payload,
            owner=model.owner,
            assigned_agent=model.assigned_agent,
            status=TaskStatus(model.status),
            parent_task_id=model.parent_task_id,
            created_at=model.created_at,
        )
