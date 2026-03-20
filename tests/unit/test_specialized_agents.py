import asyncio
import os
from pathlib import Path

from app.agents.builder import BuilderAgent
from app.agents.reader import ReaderAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.writer import WriterAgent
from app.providers.base import BaseProvider
from app.schemas.context import RunContext
from app.schemas.task import Task
from app.services.artifact_service import ArtifactService
from app.services.claim_service import ClaimService
from app.services.gap_map_service import GapMapService
from app.services.paper_card_service import PaperCardService
from app.services.run_service import RunService


class StaticProvider(BaseProvider):
    def __init__(self, payload: dict) -> None:
        self.payload = payload

    async def generate(
        self,
        system_prompt: str,
        user_input: str,
        tools=None,
        response_schema=None,
        model=None,
    ) -> dict:
        return self.payload


def test_reader_agent_registers_cards_and_spawns_mapper_task(tmp_path: Path) -> None:
    paper_cards = PaperCardService(tmp_path / "paper_cards.jsonl")
    artifacts = ArtifactService(tmp_path / "artifacts.jsonl")
    agent = ReaderAgent(
        StaticProvider(
            {
                "paper_cards": [
                    {
                        "paper_id": "p-1",
                        "title": "Test Paper",
                        "problem": "Weak retrieval grounding",
                        "setting": "open-domain QA",
                        "task_type": "retrieval",
                        "evidence_refs": [{"section": "3", "page": 4}],
                    }
                ],
                "artifact_notes": ["parsed pdf sections"],
                "uncertainties": ["appendix missing"],
                "audit_notes": ["reader completed"],
            }
        ),
        paper_card_service=paper_cards,
        artifact_service=artifacts,
    )
    task = Task(
        task_id="t-reader",
        project_id="proj",
        kind="paper_ingest",
        goal="Read source papers",
        input_payload={"topic": "retrieval"},
        owner="gabriel",
    )
    ctx = RunContext(run_id="run-reader", project_id="proj", task_id="t-reader")

    result = asyncio.run(agent.run(task, ctx))

    assert paper_cards.get_card("p-1") is not None
    assert result.next_tasks[0].kind == "gap_mapping"
    assert result.next_tasks[0].assigned_agent == "mapper_agent"
    assert result.audit_notes == ["reader completed"]


def test_builder_agent_registers_run_claims_and_review_task(tmp_path: Path) -> None:
    artifacts = ArtifactService(tmp_path / "artifacts.jsonl")
    claims = ClaimService(tmp_path / "claims.jsonl")
    runs = RunService(tmp_path / "runs.jsonl")
    agent = BuilderAgent(
        StaticProvider(
            {
                "summary": "Implemented the proposal and executed one run.",
                "artifacts": [
                    {
                        "artifact_id": "model-ckpt",
                        "kind": "checkpoint",
                        "path": "artifacts/run-builder/model.pt",
                        "hash": "abc123",
                    }
                ],
                "run_manifest": {
                    "run_id": "run-builder",
                    "spec_id": "spec-1",
                    "git_commit": "deadbeef",
                    "config_hash": "cfg123",
                    "dataset_snapshot": "data-v1",
                    "seed": 7,
                    "gpu": "A100",
                    "status": "completed",
                    "metrics": {"accuracy": 0.91},
                },
                "claims": [
                    {
                        "claim_id": "claim-1",
                        "text": "Improves accuracy by 2 points.",
                        "claim_type": "result",
                        "supported_by_tables": ["table-1"],
                        "risk_level": "medium",
                    }
                ],
                "audit_notes": ["baseline reproduced before proposal run"],
            }
        ),
        artifact_service=artifacts,
        claim_service=claims,
        run_service=runs,
    )
    task = Task(
        task_id="t-builder",
        project_id="proj",
        kind="implement_experiment",
        goal="Build the experiment",
        input_payload={"spec_id": "spec-1"},
        owner="gabriel",
    )
    ctx = RunContext(run_id="run-builder", project_id="proj", task_id="t-builder")

    result = asyncio.run(agent.run(task, ctx))

    assert runs.get_run("run-builder") is not None
    assert claims.get_claim("claim-1") is not None
    assert artifacts.list_artifacts()[0].artifact_id == "model-ckpt"
    assert result.next_tasks[0].kind == "review_build"


def test_reviewer_agent_marks_approval_requests() -> None:
    agent = ReviewerAgent(
        StaticProvider(
            {
                "decision": "needs_approval",
                "summary": "Metrics are sound but publication claim needs sign-off.",
                "blocking_issues": [],
                "audit_notes": ["human sign-off required"],
                "claim_updates": [{"claim_id": "claim-1"}],
            }
        )
    )
    task = Task(
        task_id="t-review",
        project_id="proj",
        kind="review_build",
        goal="Review the build",
        input_payload={},
        owner="gabriel",
    )
    ctx = RunContext(run_id="run-review", project_id="proj", task_id="t-review")

    result = asyncio.run(agent.run(task, ctx))

    assert result.status == "needs_approval"
    assert result.output["decision"] == "needs_approval"


def test_writer_agent_writes_artifact_and_spawns_style_task(tmp_path: Path) -> None:
    artifacts = ArtifactService(tmp_path / "artifacts.jsonl")
    agent = WriterAgent(
        StaticProvider(
            {
                "title": "ResearchOS Draft",
                "sections": [
                    {
                        "heading": "Introduction",
                        "markdown": "We study auditable research automation.",
                        "supporting_claim_ids": ["claim-1"],
                    }
                ],
                "audit_notes": ["draft generated from frozen claims"],
            }
        ),
        artifact_service=artifacts,
    )
    task = Task(
        task_id="t-writer",
        project_id="proj",
        kind="write_draft",
        goal="Write the draft",
        input_payload={},
        owner="gabriel",
    )
    ctx = RunContext(run_id="run-writer", project_id="proj", task_id="t-writer")
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = asyncio.run(agent.run(task, ctx))
    finally:
        os.chdir(cwd)

    draft_path = tmp_path / result.output["draft_artifact_path"]
    assert draft_path.exists()
    assert result.next_tasks[0].kind == "style_pass"
