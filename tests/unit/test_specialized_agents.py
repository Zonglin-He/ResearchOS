import asyncio
import os
from pathlib import Path

from app.agents.analyst import AnalystAgent
from app.agents.archivist import ArchivistAgent
from app.agents.builder import BuilderAgent
from app.agents.reader import ReaderAgent
from app.agents.reviewer import ReviewerAgent
from app.agents.verifier import VerifierAgent
from app.agents.writer import WriterAgent
from app.providers.base import BaseProvider
from app.schemas.claim import Claim
from app.schemas.context import RunContext
from app.schemas.freeze import ResultsFreeze
from app.schemas.run_manifest import RunManifest
from app.schemas.task import Task
from app.services.artifact_service import ArtifactService
from app.services.claim_service import ClaimService
from app.services.freeze_service import FreezeService
from app.services.gap_map_service import GapMapService
from app.services.lessons_service import LessonsService
from app.services.paper_card_service import PaperCardService
from app.services.run_service import RunService
from app.services.verification_service import VerificationService


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
    assert "reader completed" in result.audit_notes
    assert any(note.startswith("role assets resolved role=librarian") for note in result.audit_notes)


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
        experiment_proposal_id="proposal-1",
    )
    ctx = RunContext(run_id="run-builder", project_id="proj", task_id="t-builder")

    result = asyncio.run(agent.run(task, ctx))

    persisted_run = runs.get_run("run-builder")
    assert persisted_run is not None
    assert persisted_run.experiment_proposal_id == "proposal-1"
    assert claims.get_claim("claim-1") is not None
    assert artifacts.list_artifacts()[0].artifact_id == "model-ckpt"
    assert result.next_tasks[0].kind == "analyze_run"
    assert result.next_tasks[0].assigned_agent == "analyst_agent"


def test_builder_agent_surfaces_baseline_first_context() -> None:
    agent = BuilderAgent(StaticProvider({"summary": "unused", "run_manifest": {
        "run_id": "run-builder",
        "spec_id": "spec-1",
        "git_commit": "deadbeef",
        "config_hash": "cfg123",
        "dataset_snapshot": "data-v1",
        "seed": 7,
        "gpu": "cpu",
    }}))
    task = Task(
        task_id="t-builder-baseline",
        project_id="proj",
        kind="implement_experiment",
        goal="Patch a baseline implementation",
        input_payload={
            "baseline_repo": "https://github.com/example/baseline",
            "baseline_run_id": "run-baseline",
            "baseline_delta": "replace loss with robust variant",
            "refine_patch": {"target": "loss_fn", "change_description": "swap in robust loss"},
        },
        owner="gabriel",
    )
    ctx = RunContext(run_id="run-builder-baseline", project_id="proj", task_id="t-builder-baseline")

    payload = agent.build_user_payload(task, ctx)

    assert payload["builder_focus"]["execution_mode"] == "baseline_adaptation"
    assert payload["builder_focus"]["baseline_context"]["baseline_repo"] == "https://github.com/example/baseline"
    assert "prefer reusing or patching an existing baseline" in payload["builder_focus"]["hard_constraints"][3]


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
    artifact_kinds = {artifact.kind for artifact in artifacts.list_artifacts()}
    assert "draft_markdown" in artifact_kinds
    assert "citation_verification_report" in artifact_kinds
    assert result.next_tasks[0].kind == "style_pass"


def test_writer_agent_loads_registered_imported_runs_and_results_freeze(tmp_path: Path) -> None:
    artifacts = ArtifactService(tmp_path / "artifacts.jsonl")
    runs = RunService(tmp_path / "runs.jsonl")
    freezes = FreezeService(tmp_path / "freezes")
    runs.register_run(
        RunManifest(
            run_id="run-imported",
            spec_id="spec-1",
            git_commit="external",
            config_hash="cfg-imported",
            dataset_snapshot="dataset-v1",
            seed=3,
            gpu="external",
            status="completed",
            metrics={"accuracy": 0.87},
            source_type="imported",
            source_label="baseline-paper",
            source_metadata={"repo": "https://github.com/example/baseline"},
            notes=["Imported from an external baseline reproduction."],
        )
    )
    freezes.save_results_freeze(
        ResultsFreeze(
            results_id="results-imported",
            spec_id="spec-1",
            main_claims=["claim-1"],
            supporting_run_ids=["run-imported"],
            external_sources=["table:paper-main"],
            notes=["Imported evidence package."],
        )
    )
    agent = WriterAgent(
        StaticProvider(
            {
                "title": "Imported Draft",
                "sections": [{"heading": "Results", "markdown": "Imported run evidence.", "supporting_claim_ids": ["claim-1"]}],
                "citations": [],
            }
        ),
        artifact_service=artifacts,
        run_service=runs,
        freeze_service=freezes,
    )
    task = Task(
        task_id="t-writer-imported",
        project_id="proj",
        kind="write_draft",
        goal="Write from imported evidence",
        input_payload={"results_id": "results-imported", "imported_run_ids": ["run-imported"]},
        owner="gabriel",
    )
    ctx = RunContext(run_id="run-writer-imported", project_id="proj", task_id="t-writer-imported")

    payload = agent.build_user_payload(task, ctx)

    evidence_sources = payload["writer_focus"]["evidence_sources"]
    assert evidence_sources["registered_runs"][0]["source_type"] == "imported"
    assert evidence_sources["registered_runs"][0]["source_label"] == "baseline-paper"
    assert evidence_sources["results_freeze"]["supporting_run_ids"] == ["run-imported"]
    assert evidence_sources["results_freeze"]["external_sources"] == ["table:paper-main"]
    assert evidence_sources["verified_metrics_registry"]["entries"][0]["numeric_value"] == 0.87


def test_writer_agent_blocks_ungrounded_numeric_claims(tmp_path: Path) -> None:
    artifacts = ArtifactService(tmp_path / "artifacts.jsonl")
    runs = RunService(tmp_path / "runs.jsonl")
    runs.register_run(
        RunManifest(
            run_id="run-grounded",
            spec_id="spec-1",
            git_commit="abc123",
            config_hash="cfg",
            dataset_snapshot="dataset",
            seed=1,
            gpu="cpu",
            status="completed",
            metrics={"accuracy": 0.87},
        )
    )
    agent = WriterAgent(
        StaticProvider(
            {
                "title": "Numeric Draft",
                "sections": [
                    {
                        "heading": "Results",
                        "markdown": "Our method reaches 0.91 accuracy on the benchmark.",
                        "supporting_claim_ids": ["claim-1"],
                    }
                ],
                "citations": [],
            }
        ),
        artifact_service=artifacts,
        run_service=runs,
    )
    task = Task(
        task_id="t-writer-grounding",
        project_id="proj",
        kind="write_draft",
        goal="Write from grounded evidence",
        input_payload={"supporting_run_ids": ["run-grounded"]},
        owner="gabriel",
    )
    ctx = RunContext(run_id="run-writer-grounding", project_id="proj", task_id="t-writer-grounding")
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = asyncio.run(agent.run(task, ctx))
    finally:
        os.chdir(cwd)

    assert result.status == "handoff"
    assert result.next_tasks[0].input_payload["metric_grounding_feedback"][0]["token"] == "0.91"
    artifact_kinds = {artifact.kind for artifact in artifacts.list_artifacts()}
    assert "verified_metrics_registry" in artifact_kinds
    assert "metric_grounding_report" in artifact_kinds


def test_analyst_agent_writes_result_summary_artifact(tmp_path: Path) -> None:
    artifacts = ArtifactService(tmp_path / "artifacts.jsonl")
    agent = AnalystAgent(
        StaticProvider(
            {
                "summary": "Run looks stable overall.",
                "anomalies": ["small variance spike"],
                "recommended_actions": ["repeat with a second seed"],
                "audit_notes": ["analysis completed"],
            }
        ),
        artifact_service=artifacts,
    )
    task = Task(
        task_id="t-analyst",
        project_id="proj",
        kind="analyze_results",
        goal="Analyze results",
        input_payload={"run_id": "run-1"},
        owner="gabriel",
    )
    ctx = RunContext(run_id="run-analyst", project_id="proj", task_id="t-analyst")
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = asyncio.run(agent.run(task, ctx))
    finally:
        os.chdir(cwd)

    assert result.artifacts
    assert artifacts.list_artifacts()[0].kind == "result_summary"
    assert result.output["recommended_actions"] == ["repeat with a second seed"]


def test_verifier_agent_records_verification_and_writes_report(tmp_path: Path) -> None:
    artifacts = ArtifactService(tmp_path / "artifacts.jsonl")
    claims = ClaimService(tmp_path / "claims.jsonl")
    runs = RunService(tmp_path / "runs.jsonl")
    freezes = FreezeService(tmp_path / "freezes")
    verification = VerificationService(
        run_service=runs,
        artifact_service=artifacts,
        claim_service=claims,
        freeze_service=freezes,
        registry_path=tmp_path / "verifications.jsonl",
    )
    runs.register_run(
        RunManifest(
            run_id="run-verify",
            spec_id="spec-1",
            git_commit="abc123",
            config_hash="cfg",
            dataset_snapshot="dataset",
            seed=1,
            gpu="cpu",
        )
    )
    agent = VerifierAgent(
        StaticProvider(
            {
                "summary": "Verification report generated.",
                "recommendations": ["register any missing artifacts before publication"],
                "audit_notes": ["verification completed"],
            }
        ),
        verification_service=verification,
        artifact_service=artifacts,
    )
    task = Task(
        task_id="t-verifier",
        project_id="proj",
        kind="verify_evidence",
        goal="Verify run evidence",
        input_payload={"run_id": "run-verify"},
        owner="gabriel",
    )
    ctx = RunContext(run_id="run-verifier", project_id="proj", task_id="t-verifier")
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = asyncio.run(agent.run(task, ctx))
    finally:
        os.chdir(cwd)

    records = verification.list_checks(subject_type="run", subject_id="run-verify")
    assert records
    assert result.output["verification_status"] == records[0].status.value
    assert artifacts.list_artifacts()[0].kind == "verification_report"


def test_archivist_agent_records_lessons_and_archive_entry(tmp_path: Path) -> None:
    lessons = LessonsService(tmp_path / "lessons.jsonl")
    artifacts = ArtifactService(tmp_path / "artifacts.jsonl")
    agent = ArchivistAgent(
        StaticProvider(
            {
                "summary": "Archive the experiment context and next-step lesson.",
                "lessons": [
                    {
                        "title": "Capture baseline assumptions",
                        "summary": "Baseline assumptions should be written before the next iteration.",
                        "recommended_action": "Record baseline deltas explicitly.",
                        "lesson_kind": "lesson",
                        "evidence_refs": ["task:t-archivist"],
                    }
                ],
                "provenance_notes": ["Linked to result summary and verification report."],
                "audit_notes": ["archive completed"],
            }
        ),
        lessons_service=lessons,
        artifact_service=artifacts,
    )
    task = Task(
        task_id="t-archivist",
        project_id="proj",
        kind="archive_research",
        goal="Archive lessons",
        input_payload={},
        owner="gabriel",
    )
    ctx = RunContext(run_id="run-archivist", project_id="proj", task_id="t-archivist")
    cwd = os.getcwd()
    os.chdir(tmp_path)
    try:
        result = asyncio.run(agent.run(task, ctx))
    finally:
        os.chdir(cwd)

    assert lessons.list_lessons(agent_name="archivist_agent")
    assert result.output["lesson_ids"]
    assert artifacts.list_artifacts()[0].kind == "archive_entry"
