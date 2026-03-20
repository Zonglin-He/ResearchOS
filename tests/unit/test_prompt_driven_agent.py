from app.agents.reader import ReaderAgent
from app.providers.base import BaseProvider
from app.schemas.context import RunContext
from app.schemas.task import Task


class FakeProvider(BaseProvider):
    async def generate(
        self,
        system_prompt: str,
        user_input: str,
        tools=None,
        response_schema=None,
        model=None,
    ) -> dict:
        return {"echo": "ok", "system_prompt": system_prompt[:20], "user_input": user_input[:20]}


def test_prompt_driven_agent_returns_agent_result() -> None:
    import asyncio

    agent = ReaderAgent(FakeProvider())
    task = Task(
        task_id="t1",
        project_id="p1",
        kind="paper_ingest",
        goal="Ingest a paper",
        input_payload={},
        owner="gabriel",
    )
    context = RunContext(run_id="run-1", project_id="p1", task_id="t1")

    result = asyncio.run(agent.run(task, context))

    assert result.status == "success"
    assert result.output["paper_cards"] == []
    assert result.output["uncertainties"] == []
