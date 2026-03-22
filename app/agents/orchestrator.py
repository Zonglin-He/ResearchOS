from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.agents.base import BaseAgent
from app.core.enums import Stage
from app.routing.models import ResolvedDispatch
from app.routing.resolver import RoutingResolver
from app.schemas.activity import RunEvent
from app.schemas.context import RunContext
from app.schemas.result import AgentResult
from app.schemas.task import Task, TaskStatus
from app.services.activity_service import ActivityService
from app.services.checkpoint_service import CheckpointService
from app.services.project_service import ProjectService
from app.services.task_service import TaskService
from app.services.lessons_service import LessonsService


@dataclass
class OrchestratorDispatch:
    task: Task
    result: AgentResult


class Orchestrator:
    def __init__(
        self,
        task_service: TaskService,
        project_service: ProjectService | None = None,
        routing_resolver: RoutingResolver | None = None,
        lessons_service: LessonsService | None = None,
        artifacts_dir: str | Path = "artifacts",
        activity_service: ActivityService | None = None,
        checkpoint_service: CheckpointService | None = None,
    ) -> None:
        self.task_service = task_service
        self.project_service = project_service
        self.routing_resolver = routing_resolver
        self.lessons_service = lessons_service
        self.artifacts_dir = Path(artifacts_dir)
        self.activity_service = activity_service
        self.checkpoint_service = checkpoint_service
        self._agents: dict[str, BaseAgent] = {}
        self._kind_to_agent: dict[str, str] = {}

    def register_agent(self, agent: BaseAgent, *, handles: set[str] | None = None) -> None:
        self._agents[agent.name] = agent
        for kind in handles or set():
            self._kind_to_agent[kind] = agent.name

    def preview_routing(self, task_id: str) -> ResolvedDispatch | None:
        task = self.task_service.get_task(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        agent_name = task.assigned_agent or self._kind_to_agent.get(task.kind)
        if agent_name is None:
            return task.last_run_routing
        agent = self._agents.get(agent_name)
        if agent is None:
            raise KeyError(f"Agent not found: {agent_name}")
        return self._resolve_routing(task, agent)

    async def dispatch(self, task_id: str) -> OrchestratorDispatch:
        task = self.task_service.get_task(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        if not self.task_service.dependencies_satisfied(task):
            dependency_ids = []
            for dependency_id in task.depends_on:
                dependency = self.task_service.get_task(dependency_id)
                if dependency is None or dependency.status != TaskStatus.SUCCEEDED:
                    dependency_ids.append(dependency_id)
            self._record_event(
                task.project_id,
                event_type="task.dependency_blocked",
                message=f"Task {task.task_id} is blocked by unsatisfied dependencies",
                task_id=task.task_id,
                payload={"depends_on": dependency_ids},
            )
            raise ValueError(f"Task dependencies are not satisfied: {dependency_ids}")
        if task.next_retry_at is not None and not self.task_service.is_runnable(task):
            raise ValueError(
                f"Task retry is scheduled for {task.next_retry_at.isoformat()}; it is not runnable yet"
            )

        agent_name = task.assigned_agent or self._kind_to_agent.get(task.kind)
        if agent_name is None:
            raise ValueError(f"No agent registered for task kind: {task.kind}")

        agent = self._agents.get(agent_name)
        if agent is None:
            raise KeyError(f"Agent not found: {agent_name}")

        routing = self._resolve_routing(task, agent)
        if task.status != TaskStatus.RUNNING:
            task = self.task_service.update_status(task.task_id, TaskStatus.RUNNING)
        task.assigned_agent = agent_name
        task.last_run_routing = routing
        task.next_retry_at = None
        task = self.task_service.save_task(task)

        checkpoint_path = self._save_checkpoint(
            task,
            stage="dispatch_started",
            payload={"routing": self._routing_record(routing), "agent_name": agent_name},
        )
        context = RunContext(
            run_id=f"run-{task.task_id}",
            project_id=task.project_id,
            task_id=task.task_id,
            artifacts_dir=str(self.artifacts_dir),
            max_steps=routing.max_steps if routing is not None and routing.max_steps is not None else 12,
            routing=routing,
            prior_lessons=self._resolve_prior_lessons(task, agent_name, routing),
            checkpoint_dir=str(self.checkpoint_service.root_dir) if self.checkpoint_service is not None else "",
            checkpoint_path=checkpoint_path,
            resume_from_checkpoint=self._load_checkpoint(task.task_id),
            checkpoint_recorder=lambda stage, payload: self._save_checkpoint(task, stage=stage, payload=payload),
        )
        self._record_event(
            task.project_id,
            event_type="task.dispatched",
            message=f"Dispatch started for task {task.task_id}",
            task_id=task.task_id,
            run_id=context.run_id,
            payload={"agent_name": agent_name, "routing": self._routing_record(routing)},
        )
        try:
            result = await agent.run(task, context)
        except Exception as error:
            task = self.task_service.mark_task_failed(
                task.task_id,
                error_detail=str(error),
                retryable=True,
            )
            task.checkpoint_path = self._save_checkpoint(
                task,
                stage="dispatch_failed",
                payload={"error": str(error), "agent_name": agent_name},
            )
            task = self.task_service.save_task(task)
            result = AgentResult(
                status="fail",
                output={"error": str(error)},
                audit_notes=[f"dispatch failed: {error}"],
            )
            return OrchestratorDispatch(task=task, result=result)

        if context.routing is not None:
            result.routing = context.routing
            task.last_run_routing = context.routing
            task = self.task_service.save_task(task)
            result.audit_notes.append(self._routing_audit_note(context.routing))
        if self.lessons_service is not None:
            self.lessons_service.capture_agent_outcome(
                task=task,
                agent_name=agent_name,
                result=result,
            )

        final_status = self._result_to_status(result.status)
        task = self._create_next_tasks(task, result.next_tasks)
        if final_status is not None:
            task = self.task_service.update_status(task.task_id, final_status)
        self._sync_project_stage(task, result)
        task.checkpoint_path = self._save_checkpoint(
            task,
            stage=f"dispatch_{result.status}",
            payload={
                "artifacts": list(result.artifacts),
                "output": result.output,
                "next_tasks": [next_task.task_id for next_task in result.next_tasks],
                "audit_notes": list(result.audit_notes),
            },
        )
        task = self.task_service.save_task(task)
        self._record_event(
            task.project_id,
            event_type="task.completed",
            message=f"Dispatch finished for task {task.task_id} with status {task.status.value}",
            task_id=task.task_id,
            run_id=context.run_id,
            payload={
                "status": task.status.value,
                "artifacts": list(result.artifacts),
                "next_tasks": [next_task.task_id for next_task in result.next_tasks],
            },
        )

        return OrchestratorDispatch(task=task, result=result)

    def _resolve_routing(self, task: Task, agent: BaseAgent) -> ResolvedDispatch | None:
        if self.routing_resolver is None:
            return task.last_run_routing
        project = None
        if self.project_service is not None:
            project = self.project_service.get_project(task.project_id)
        return self.routing_resolver.resolve(
            task=task,
            project=project,
            agent_policy=getattr(agent, "routing_policy", None),
        )

    def _resolve_prior_lessons(
        self,
        task: Task,
        agent_name: str,
        routing: ResolvedDispatch | None,
    ):
        if self.lessons_service is None:
            return []
        return self.lessons_service.get_relevant_lessons(
            task_kind=task.kind,
            agent_name=agent_name,
            provider_name=routing.provider_name if routing is not None else None,
            model_name=routing.model if routing is not None else None,
            repository_ref=task.input_payload.get("repository"),
            dataset_ref=task.input_payload.get("dataset_snapshot")
            or task.input_payload.get("dataset"),
        )

    def _create_next_tasks(self, task: Task, next_tasks: list[Task]) -> Task:
        for next_task in next_tasks:
            if task.task_id not in next_task.depends_on:
                next_task.depends_on = [*next_task.depends_on, task.task_id]
            if next_task.parent_task_id is None:
                next_task.parent_task_id = task.task_id
            self.task_service.create_task(next_task)
        return task

    def _save_checkpoint(self, task: Task, *, stage: str, payload: dict[str, object]) -> str | None:
        if self.checkpoint_service is None:
            return None
        checkpoint_path = self.checkpoint_service.save(task=task, stage=stage, payload=payload)
        self._record_event(
            task.project_id,
            event_type="checkpoint.saved",
            message=f"Checkpoint saved for {task.task_id}: {stage}",
            task_id=task.task_id,
            payload={"stage": stage, "checkpoint_path": checkpoint_path},
        )
        return checkpoint_path

    def _load_checkpoint(self, task_id: str) -> dict[str, object] | None:
        if self.checkpoint_service is None:
            return None
        return self.checkpoint_service.load(task_id)

    def _sync_project_stage(self, task: Task, result: AgentResult) -> None:
        if self.project_service is None:
            return
        stage = self._stage_for_task(task, result)
        if stage is None:
            return
        self.project_service.update_stage(task.project_id, stage)

    def _record_event(
        self,
        project_id: str,
        *,
        event_type: str,
        message: str,
        task_id: str | None = None,
        run_id: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        if self.activity_service is None:
            return
        self.activity_service.record_event(
            RunEvent(
                project_id=project_id,
                task_id=task_id,
                run_id=run_id,
                event_type=event_type,
                message=message,
                payload=dict(payload or {}),
            )
        )

    @staticmethod
    def _routing_record(routing: ResolvedDispatch | None) -> dict[str, object] | None:
        if routing is None:
            return None
        return {
            "provider_name": routing.provider_name,
            "model": routing.model,
            "role_name": routing.role_name,
            "capability_class": routing.capability_class,
            "max_steps": routing.max_steps,
        }

    @staticmethod
    def _routing_audit_note(routing: ResolvedDispatch) -> str:
        return (
            "dispatch routing resolved "
            f"role={routing.role_name or '<unknown>'} "
            f"capability={routing.capability_class or '<unknown>'} "
            f"provider={routing.provider_name} "
            f"model={routing.model or '<default>'} "
            f"decision_reason={routing.decision_reason or '<none>'} "
            f"fallback_reason={routing.fallback_reason or '<none>'} "
            f"sources={routing.sources}"
        )

    @staticmethod
    def _result_to_status(result_status: str) -> TaskStatus | None:
        if result_status == "success":
            return TaskStatus.SUCCEEDED
        if result_status == "fail":
            return TaskStatus.FAILED
        if result_status == "needs_approval":
            return TaskStatus.WAITING_APPROVAL
        if result_status == "handoff":
            return TaskStatus.BLOCKED
        return None

    @staticmethod
    def _stage_for_task(task: Task, result: AgentResult) -> Stage | None:
        if task.kind == "paper_ingest":
            return Stage.INGEST_PAPERS
        if task.kind == "gap_mapping":
            if any(next_task.kind == "human_select" for next_task in result.next_tasks):
                return Stage.HUMAN_SELECT
            return Stage.MAP_GAPS
        if task.kind == "human_select":
            return Stage.FREEZE_TOPIC
        if task.kind in {"build_spec", "implement_experiment", "reproduce_baseline"}:
            return Stage.RUN_EXPERIMENTS if task.status == TaskStatus.SUCCEEDED else Stage.IMPLEMENT_IDEA
        if task.kind == "analyze_run":
            return Stage.AUDIT_RESULTS
        if task.kind in {"review_build", "audit_run"}:
            return Stage.REVIEW_DRAFT
        if task.kind == "draft_write":
            return Stage.WRITE_DRAFT
        if task.kind == "style_pass":
            return Stage.SUBMISSION_READY if task.status == TaskStatus.SUCCEEDED else Stage.STYLE_PASS
        return None
