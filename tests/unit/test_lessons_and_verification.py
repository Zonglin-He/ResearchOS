from pathlib import Path

from app.agents.base import BaseAgent
from app.agents.orchestrator import Orchestrator
from app.db.repositories.in_memory_task_repository import InMemoryTaskRepository
from app.schemas.artifact import ArtifactRecord
from app.schemas.lesson import LessonKind, LessonRecord
from app.schemas.result import AgentResult
from app.schemas.run_manifest import RunManifest
from app.schemas.task import Task, TaskStatus
from app.services.artifact_service import ArtifactService
from app.services.claim_service import ClaimService
from app.services.freeze_service import FreezeService
from app.services.lessons_service import LessonsService
from app.services.run_service import RunService
from app.services.task_service import TaskService
from app.services.verification_service import VerificationService


class FailingAgent(BaseAgent):
    name = "reviewer_agent"
    description = "Fails and records prior lessons"

    def __init__(self) -> None:
        self.prior_lessons_count = 0

    async def run(self, task: Task, ctx) -> AgentResult:
        self.prior_lessons_count = len(ctx.prior_lessons)
        return AgentResult(
            status="fail",
            output={"blocking_issues": ["Missing ablation for baseline comparison."]},
            artifacts=["artifact-review-note"],
            audit_notes=["Previous runs failed because ablations were omitted."],
        )


def test_lessons_service_records_and_filters_lessons(tmp_path: Path) -> None:
    service = LessonsService(tmp_path / "lessons.jsonl")
    service.record_lesson(
        LessonRecord(
            lesson_id="lesson-1",
            lesson_kind=LessonKind.FAILURE_SIGNATURE,
            title="Missing baseline ablation",
            summary="Builder skipped the baseline ablation and produced a weak comparison.",
            task_kind="implement_experiment",
            agent_name="builder_agent",
            provider_name="codex",
            model_name="gpt-5.4",
            failure_type="ablation_gap",
            dataset_ref="dataset-v1",
        )
    )
    service.record_lesson(
        LessonRecord(
            lesson_id="lesson-2",
            lesson_kind=LessonKind.PLAYBOOK,
            title="Reader prompt structure",
            summary="Reader performs better when the source summary includes setting and baseline.",
            task_kind="paper_ingest",
            agent_name="reader_agent",
            provider_name="claude",
            model_name="sonnet",
        )
    )

    filtered = service.list_lessons(
        task_kind="implement_experiment",
        provider_name="codex",
        failure_type="ablation_gap",
    )

    assert len(filtered) == 1
    assert filtered[0].lesson_id == "lesson-1"


def test_verification_service_verifies_run_manifest_and_artifacts(tmp_path: Path) -> None:
    run_service = RunService(tmp_path / "runs.jsonl")
    artifact_service = ArtifactService(tmp_path / "artifacts.jsonl")
    verification_service = VerificationService(
        run_service=run_service,
        artifact_service=artifact_service,
        claim_service=ClaimService(tmp_path / "claims.jsonl"),
        freeze_service=FreezeService(tmp_path / "freezes"),
        registry_path=tmp_path / "verifications.jsonl",
    )
    run_service.register_run(
        RunManifest(
            run_id="run-1",
            spec_id="spec-1",
            git_commit="abc123",
            config_hash="cfg",
            dataset_snapshot="dataset-v1",
            seed=7,
            gpu="A100",
            artifacts=["artifact-1"],
        )
    )
    artifact_service.register_artifact(
        ArtifactRecord(
            artifact_id="artifact-1",
            run_id="run-1",
            kind="table",
            path="artifacts/table.csv",
            hash="sha256:table",
        )
    )

    record = verification_service.verify_run_manifest("run-1")

    assert record.status.value == "verified"
    assert verification_service.list_checks(subject_type="run")[0].subject_id == "run-1"


def test_orchestrator_loads_prior_lessons_and_captures_failure_lesson(tmp_path: Path) -> None:
    task_service = TaskService(InMemoryTaskRepository())
    lessons_service = LessonsService(tmp_path / "lessons.jsonl")
    lessons_service.record_lesson(
        LessonRecord(
            lesson_id="lesson-prior",
            lesson_kind=LessonKind.FAILURE_SIGNATURE,
            title="Ablation omission",
            summary="Always include the baseline ablation before declaring improvement.",
            task_kind="audit_run",
            agent_name="reviewer_agent",
            provider_name="claude",
            model_name="sonnet",
        )
    )
    orchestrator = Orchestrator(task_service, lessons_service=lessons_service)
    agent = FailingAgent()
    orchestrator.register_agent(agent, handles={"audit_run"})
    task_service.create_task(
        Task(
            task_id="t1",
            project_id="p1",
            kind="audit_run",
            goal="Review run quality",
            input_payload={},
            owner="tester",
        )
    )

    import asyncio

    dispatch = asyncio.run(orchestrator.dispatch("t1"))

    assert agent.prior_lessons_count == 1
    assert dispatch.task.status == TaskStatus.FAILED
    lessons = lessons_service.list_lessons(task_kind="audit_run", agent_name="reviewer_agent")
    assert len(lessons) == 2
    assert any(lesson.source_task_id == "t1" for lesson in lessons)
