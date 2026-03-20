from pathlib import Path

from app.db.repositories.in_memory_task_repository import InMemoryTaskRepository
from app.schemas.experiment import (
    ExperimentBudget,
    ExperimentDecisionKind,
    ExperimentProposal,
    ExperimentResultSummary,
)
from app.schemas.freeze import SpecFreeze
from app.schemas.project import Project
from app.schemas.run_manifest import RunManifest
from app.schemas.task import Task
from app.services.approval_service import ApprovalService
from app.services.experiment_manager import ExperimentManager
from app.services.experiment_registry import ExperimentRegistry
from app.services.freeze_service import FreezeService
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.services.task_service import TaskService


def build_manager(tmp_path: Path) -> tuple[ExperimentManager, TaskService, ApprovalService, RunService, FreezeService]:
    task_service = TaskService(InMemoryTaskRepository())
    approval_service = ApprovalService(tmp_path / "approvals.jsonl")
    run_service = RunService(tmp_path / "runs.jsonl")
    freeze_service = FreezeService(tmp_path / "freezes")
    manager = ExperimentManager(
        registry=ExperimentRegistry(tmp_path / "experiments"),
        task_service=task_service,
        run_service=run_service,
        freeze_service=freeze_service,
        approval_service=approval_service,
    )
    return manager, task_service, approval_service, run_service, freeze_service


def test_experiment_manager_requires_approval_for_expensive_proposal(tmp_path: Path) -> None:
    manager, task_service, approval_service, _, freeze_service = build_manager(tmp_path)
    freeze_service.save_spec_freeze(
        SpecFreeze(spec_id="spec-1", topic_id="topic-1", status="approved")
    )
    task_service.create_task(
        Task(
            task_id="t1",
            project_id="p1",
            kind="implement_experiment",
            goal="Run expensive experiment",
            input_payload={},
            owner="tester",
        )
    )
    proposal = ExperimentProposal(
        proposal_id="proposal-1",
        task_id="t1",
        spec_id="spec-1",
        title="Expensive run",
        hypothesis="Higher-capacity model improves results",
        proposed_by="builder_agent",
        execution_command="python train.py",
        objective_metric="accuracy",
        estimated_cost=80.0,
        branch_name="exp/proposal-1",
    )
    budget = ExperimentBudget(spec_id="spec-1", require_approval_above=50.0)

    manager.enqueue_proposal(task_id="t1", proposal=proposal, budget=budget)
    decision = manager.authorize_execution("proposal-1")

    assert decision is not None
    assert decision.decision == ExperimentDecisionKind.REQUIRES_APPROVAL
    approvals = approval_service.list_pending()
    assert approvals[0].target_id == "proposal-1"
    task = task_service.get_task("t1")
    assert task is not None
    assert task.experiment_proposal_id == "proposal-1"


def test_experiment_manager_blocks_without_approved_spec_freeze(tmp_path: Path) -> None:
    manager, task_service, _, _, _ = build_manager(tmp_path)
    task_service.create_task(
        Task(
            task_id="t1",
            project_id="p1",
            kind="implement_experiment",
            goal="Run experiment",
            input_payload={},
            owner="tester",
        )
    )
    proposal = ExperimentProposal(
        proposal_id="proposal-2",
        task_id="t1",
        spec_id="spec-missing",
        title="Run without spec freeze",
        hypothesis="Should be blocked",
        proposed_by="builder_agent",
        execution_command="python train.py",
        objective_metric="accuracy",
    )
    budget = ExperimentBudget(spec_id="spec-missing")

    manager.enqueue_proposal(task_id="t1", proposal=proposal, budget=budget)
    decision = manager.authorize_execution("proposal-2")

    assert decision is not None
    assert decision.decision == ExperimentDecisionKind.BLOCK
    assert "Spec freeze" in decision.reason


def test_experiment_manager_records_execution_and_discards_on_no_improvement(tmp_path: Path) -> None:
    manager, task_service, approval_service, run_service, freeze_service = build_manager(tmp_path)
    freeze_service.save_spec_freeze(
        SpecFreeze(spec_id="spec-1", topic_id="topic-1", status="approved")
    )
    task_service.create_task(
        Task(
            task_id="t1",
            project_id="p1",
            kind="implement_experiment",
            goal="Run experiment",
            input_payload={"branch_name": "exp/proposal-3"},
            owner="tester",
        )
    )
    proposal = ExperimentProposal(
        proposal_id="proposal-3",
        task_id="t1",
        spec_id="spec-1",
        title="No-improvement run",
        hypothesis="Maybe helps",
        proposed_by="builder_agent",
        execution_command="python train.py",
        objective_metric="accuracy",
        branch_name="exp/proposal-3",
    )
    budget = ExperimentBudget(spec_id="spec-1", max_attempts=2, stop_on_no_improvement=True)

    manager.enqueue_proposal(task_id="t1", proposal=proposal, budget=budget)
    assert manager.authorize_execution("proposal-3") is None

    run_manifest = RunManifest(
        run_id="run-3",
        spec_id="spec-1",
        git_commit="deadbeef",
        config_hash="cfg",
        dataset_snapshot="data-v1",
        seed=7,
        gpu="A100",
        status="running",
    )
    record = manager.record_execution(proposal_id="proposal-3", run_manifest=run_manifest)
    decision = manager.evaluate_result(
        proposal_id="proposal-3",
        result_summary=ExperimentResultSummary(
            proposal_id="proposal-3",
            run_id="run-3",
            primary_metric="accuracy",
            primary_value=0.80,
            baseline_value=0.81,
            cost_spent=12.5,
            improved=False,
            notes=["validation accuracy regressed slightly"],
        ),
    )

    assert record.run_manifest.experiment_proposal_id == "proposal-3"
    assert record.run_manifest.experiment_branch == "exp/proposal-3"
    assert decision.decision == ExperimentDecisionKind.DISCARD
    assert decision.branch_action == "rollback_to_base"
    persisted_run = run_service.get_run("run-3")
    assert persisted_run is not None
    assert persisted_run.metrics["accuracy"] == 0.80
    assert persisted_run.metrics["improvement"] == -0.01
