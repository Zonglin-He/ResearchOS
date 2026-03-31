from __future__ import annotations

from datetime import datetime

from app.db.models import TaskModel
from app.routing import dispatch_profile_from_dict, resolved_dispatch_from_dict
from app.schemas.task import Task, TaskStatus
from app.schemas.strategy import HandoffPacket, RetrievalEvidence, StrategyTrace
from app.services.registry_store import to_record


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
            depends_on=task.depends_on,
            join_key=task.join_key,
            fanout_group=task.fanout_group,
            experiment_proposal_id=task.experiment_proposal_id,
            dispatch_profile=to_record(task.dispatch_profile),
            last_run_routing=to_record(task.last_run_routing),
            retry_count=task.retry_count,
            max_retries=task.max_retries,
            last_error=task.last_error,
            next_retry_at=task.next_retry_at,
            checkpoint_path=task.checkpoint_path,
            latest_strategy_trace=to_record(task.latest_strategy_trace),
            latest_retrieval_evidence=to_record(task.latest_retrieval_evidence),
            latest_handoff_packet=to_record(task.latest_handoff_packet),
            created_at=task.created_at,
        )

    @staticmethod
    def _to_schema(model: TaskModel) -> Task:
        strategy_payload = model.latest_strategy_trace or {}
        handoff_payload = model.latest_handoff_packet or {}
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
            depends_on=model.depends_on or [],
            join_key=model.join_key,
            fanout_group=model.fanout_group,
            experiment_proposal_id=model.experiment_proposal_id,
            dispatch_profile=dispatch_profile_from_dict(model.dispatch_profile),
            last_run_routing=resolved_dispatch_from_dict(model.last_run_routing),
            retry_count=model.retry_count,
            max_retries=model.max_retries,
            last_error=model.last_error,
            next_retry_at=model.next_retry_at,
            checkpoint_path=model.checkpoint_path,
            latest_strategy_trace=StrategyTrace(
                task_id=str(strategy_payload["task_id"]),
                project_id=str(strategy_payload["project_id"]),
                should_retrieve=bool(strategy_payload["should_retrieve"]),
                retrieval_targets=tuple(strategy_payload.get("retrieval_targets", [])),
                should_call_tools=bool(strategy_payload.get("should_call_tools", False)),
                tool_candidates=tuple(strategy_payload.get("tool_candidates", [])),
                needs_human_checkpoint=bool(strategy_payload.get("needs_human_checkpoint", False)),
                reasoning_summary=str(strategy_payload.get("reasoning_summary", "")),
                created_at=datetime.fromisoformat(str(strategy_payload["created_at"])),
            ) if model.latest_strategy_trace else None,
            latest_retrieval_evidence=[RetrievalEvidence(**item) for item in (model.latest_retrieval_evidence or [])],
            latest_handoff_packet=HandoffPacket(
                from_agent=str(handoff_payload["from_agent"]),
                to_agent=str(handoff_payload["to_agent"]),
                task_kind=str(handoff_payload["task_kind"]),
                objective=str(handoff_payload["objective"]),
                required_inputs=tuple(handoff_payload.get("required_inputs", [])),
                attached_evidence_ids=tuple(handoff_payload.get("attached_evidence_ids", [])),
                blocking_questions=tuple(handoff_payload.get("blocking_questions", [])),
                done_definition=str(handoff_payload.get("done_definition", "")),
            ) if model.latest_handoff_packet else None,
            created_at=model.created_at,
        )
