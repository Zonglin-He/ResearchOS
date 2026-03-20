import asyncio
from dataclasses import dataclass

from app.agents.mapper import MapperAgent
from app.agents.reader import ReaderAgent
from app.providers.base import BaseProvider
from app.schemas.context import RunContext
from app.schemas.paper_card import PaperCard
from app.schemas.task import Task
from app.services.gap_map_service import GapMapService
from app.services.paper_card_service import PaperCardService


class EmptyProvider(BaseProvider):
    async def generate(
        self,
        system_prompt: str,
        user_input: str,
        tools=None,
        response_schema=None,
        model=None,
    ) -> dict:
        return {}


def test_reader_fallback_generates_paper_card_from_source_summary(tmp_path) -> None:
    paper_cards = PaperCardService(tmp_path / "paper_cards.jsonl")
    agent = ReaderAgent(EmptyProvider(), paper_card_service=paper_cards)
    task = Task(
        task_id="reader-fallback",
        project_id="p1",
        kind="paper_ingest",
        goal="Read a source summary",
        input_payload={
            "topic": "retrieval",
            "source_summary": {
                "title": "Fallback Paper",
                "abstract": "A system for grounded retrieval.",
                "setting": "open-domain QA",
            },
        },
        owner="system",
    )
    ctx = RunContext(run_id="run-reader-fallback", project_id="p1", task_id="reader-fallback")

    result = asyncio.run(agent.run(task, ctx))

    assert len(result.output["paper_cards"]) == 1
    assert result.output["paper_cards"][0]["title"] == "Fallback Paper"
    assert paper_cards.list_cards()[0].title == "Fallback Paper"
    assert result.next_tasks[0].kind == "gap_mapping"


def test_mapper_fallback_generates_gap_map_from_registered_cards(tmp_path) -> None:
    paper_cards = PaperCardService(tmp_path / "paper_cards.jsonl")
    gap_maps = GapMapService(tmp_path / "gap_maps.jsonl")
    paper_cards.register_card(
        PaperCard(
            paper_id="paper-1",
            title="Fallback Paper",
            problem="Grounding is brittle",
            setting="open-domain QA",
            task_type="retrieval",
        )
    )
    agent = MapperAgent(
        EmptyProvider(),
        gap_map_service=gap_maps,
        paper_card_service=paper_cards,
    )
    task = Task(
        task_id="mapper-fallback",
        project_id="p1",
        kind="gap_mapping",
        goal="Map gaps",
        input_payload={
            "topic": "retrieval",
            "paper_ids": ["paper-1"],
        },
        owner="system",
    )
    ctx = RunContext(run_id="run-mapper-fallback", project_id="p1", task_id="mapper-fallback")

    result = asyncio.run(agent.run(task, ctx))

    assert result.output["gap_map"]["topic"] == "retrieval"
    assert result.output["gap_map"]["clusters"][0]["gaps"][0]["supporting_papers"] == ["paper-1"]
    assert result.output["ranked_candidates"][0]["gap_id"] == "gap-1"
    assert gap_maps.list_gap_maps()[0].topic == "retrieval"
