from app.agents.base import BaseAgent
from app.agents.orchestrator import Orchestrator
from app.db.repositories.in_memory_project_repository import InMemoryProjectRepository
from app.db.repositories.in_memory_task_repository import InMemoryTaskRepository
from app.routing.models import AgentRoutingPolicy, DispatchProfile, ProviderSpec
from app.routing.resolver import RoutingResolver
from app.schemas.project import Project
from app.schemas.result import AgentResult
from app.schemas.task import Task, TaskStatus
from app.services.project_service import ProjectService
from app.services.task_service import TaskService


class SuccessfulAgent(BaseAgent):
    name = "reader_agent"
    description = "Returns a successful result"
    routing_policy = AgentRoutingPolicy(
        agent_name="reader_agent",
        fallback_provider=ProviderSpec(provider_name="claude", model="sonnet"),
    )

    def __init__(self) -> None:
        self.last_routing = None

    async def run(self, task: Task, ctx) -> AgentResult:
        self.last_routing = ctx.routing
        return AgentResult(status="success")


def test_orchestrator_dispatches_task_and_updates_status() -> None:
    repository = InMemoryTaskRepository()
    task_service = TaskService(repository)
    orchestrator = Orchestrator(task_service)
    orchestrator.register_agent(SuccessfulAgent(), handles={"paper_ingest"})
    task = Task(
        task_id="t1",
        project_id="p1",
        kind="paper_ingest",
        goal="Ingest a paper",
        input_payload={},
        owner="gabriel",
    )
    task_service.create_task(task)

    import asyncio

    dispatch = asyncio.run(orchestrator.dispatch("t1"))

    assert dispatch.result.status == "success"
    assert dispatch.task.status == TaskStatus.SUCCEEDED


def test_orchestrator_persists_resolved_routing_from_task_override() -> None:
    project_repository = InMemoryProjectRepository()
    task_repository = InMemoryTaskRepository()
    project_service = ProjectService(project_repository)
    task_service = TaskService(task_repository)
    resolver = RoutingResolver(
        DispatchProfile(
            provider=ProviderSpec(provider_name="claude", model="sonnet"),
            max_steps=12,
        )
    )
    orchestrator = Orchestrator(
        task_service,
        project_service=project_service,
        routing_resolver=resolver,
    )
    agent = SuccessfulAgent()
    orchestrator.register_agent(agent, handles={"paper_ingest"})
    project_service.create_project(
        Project(
            project_id="p1",
            name="ResearchOS",
            description="routing",
            status="active",
            dispatch_profile=DispatchProfile(
                provider=ProviderSpec(provider_name="gemini", model="gemini-2.5-pro"),
            ),
        )
    )
    task_service.create_task(
        Task(
            task_id="t2",
            project_id="p1",
            kind="paper_ingest",
            goal="Ingest a paper",
            input_payload={},
            owner="gabriel",
            dispatch_profile=DispatchProfile(
                provider=ProviderSpec(provider_name="codex", model="gpt-5.4"),
                max_steps=22,
            ),
        )
    )

    import asyncio

    dispatch = asyncio.run(orchestrator.dispatch("t2"))

    assert agent.last_routing is not None
    assert agent.last_routing.provider_name == "codex"
    assert agent.last_routing.model == "gpt-5.4"
    assert agent.last_routing.max_steps == 22
    assert dispatch.task.last_run_routing is not None
    assert dispatch.task.last_run_routing.provider_name == "codex"
    assert dispatch.result.routing is not None
    assert dispatch.result.routing.provider_name == "codex"
    assert any("provider=codex" in note for note in dispatch.result.audit_notes)
