from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.agents.base import BaseAgent
from app.routing.models import ResolvedDispatch
from app.routing.resolver import RoutingResolver
from app.schemas.context import RunContext
from app.schemas.result import AgentResult
from app.schemas.task import Task, TaskStatus
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
    ) -> None:
        self.task_service = task_service
        self.project_service = project_service
        self.routing_resolver = routing_resolver
        self.lessons_service = lessons_service
        self.artifacts_dir = Path(artifacts_dir)
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
        task = self.task_service.repository.update(task)

        context = RunContext(
            run_id=f"run-{task.task_id}",
            project_id=task.project_id,
            task_id=task.task_id,
            artifacts_dir=str(self.artifacts_dir),
            max_steps=routing.max_steps if routing is not None and routing.max_steps is not None else 12,
            routing=routing,
            prior_lessons=self._resolve_prior_lessons(task, agent_name, routing),
        )
        result = await agent.run(task, context)
        if context.routing is not None:
            result.routing = context.routing
            task.last_run_routing = context.routing
            task = self.task_service.repository.update(task)
            result.audit_notes.append(self._routing_audit_note(context.routing))
        if self.lessons_service is not None:
            self.lessons_service.capture_agent_outcome(
                task=task,
                agent_name=agent_name,
                result=result,
            )

        for next_task in result.next_tasks:
            self.task_service.create_task(next_task)

        final_status = self._result_to_status(result.status)
        if final_status is not None:
            task = self.task_service.update_status(task.task_id, final_status)
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
