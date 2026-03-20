from __future__ import annotations

from dataclasses import dataclass

from app.agents.base import BaseAgent
from app.schemas.context import RunContext
from app.schemas.result import AgentResult
from app.schemas.task import Task, TaskStatus
from app.services.task_service import TaskService


@dataclass
class OrchestratorDispatch:
    task: Task
    result: AgentResult


class Orchestrator:
    def __init__(self, task_service: TaskService) -> None:
        self.task_service = task_service
        self._agents: dict[str, BaseAgent] = {}
        self._kind_to_agent: dict[str, str] = {}

    def register_agent(self, agent: BaseAgent, *, handles: set[str] | None = None) -> None:
        self._agents[agent.name] = agent
        for kind in handles or set():
            self._kind_to_agent[kind] = agent.name

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

        if task.status != TaskStatus.RUNNING:
            task = self.task_service.update_status(task.task_id, TaskStatus.RUNNING)
        task.assigned_agent = agent_name
        task = self.task_service.repository.update(task)

        context = RunContext(
            run_id=f"run-{task.task_id}",
            project_id=task.project_id,
            task_id=task.task_id,
        )
        result = await agent.run(task, context)

        for next_task in result.next_tasks:
            self.task_service.create_task(next_task)

        final_status = self._result_to_status(result.status)
        if final_status is not None:
            task = self.task_service.update_status(task.task_id, final_status)
        return OrchestratorDispatch(task=task, result=result)

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
