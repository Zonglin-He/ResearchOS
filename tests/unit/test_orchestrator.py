from app.agents.base import BaseAgent
from app.agents.orchestrator import Orchestrator
from app.db.repositories.in_memory_task_repository import InMemoryTaskRepository
from app.schemas.result import AgentResult
from app.schemas.task import Task, TaskStatus
from app.services.task_service import TaskService


class SuccessfulAgent(BaseAgent):
    name = "reader_agent"
    description = "Returns a successful result"

    async def run(self, task: Task, ctx) -> AgentResult:
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
