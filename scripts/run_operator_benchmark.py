from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.db.repositories.in_memory_project_repository import InMemoryProjectRepository
from app.db.repositories.in_memory_task_repository import InMemoryTaskRepository
from app.schemas.activity import RunEvent
from app.schemas.project import Project
from app.schemas.run_manifest import RunManifest
from app.schemas.task import Task, TaskStatus
from app.services.activity_service import ActivityService
from app.services.checkpoint_service import CheckpointService
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.services.task_service import TaskService
from app.workflows.research_flow import FlowEvent, available_flow_actions, stage_for_task_kind


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="researchos-benchmark-") as tmp_dir:
        root = Path(tmp_dir)
        activity_service = ActivityService(events_path=root / "state" / "run_events.jsonl")
        checkpoint_service = CheckpointService(root / "artifacts" / "checkpoints")
        project_service = ProjectService(InMemoryProjectRepository())
        task_service = TaskService(InMemoryTaskRepository(), activity_service=activity_service)
        run_service = RunService(root / "registry" / "runs.jsonl")

        project = project_service.create_project(
            Project(
                project_id="bench-project",
                name="Operator Benchmark",
                description="Smoke benchmark for flow, events, resume, and branch compare.",
                status="active",
            )
        )
        task = task_service.create_task(
            Task(
                task_id="bench-task",
                project_id=project.project_id,
                kind="paper_ingest",
                goal="Read one bounded source",
                input_payload={"topic": "operator benchmark"},
                owner="benchmark",
            )
        )

        project_service.transition_flow(
            project.project_id,
            event=FlowEvent.START,
            stage=stage_for_task_kind(task.kind),
            task_id=task.task_id,
            note="benchmark dispatch started",
        )
        checkpoint_path = checkpoint_service.save(
            task=task,
            stage="dispatch_started",
            payload={"benchmark": True},
        )
        task.checkpoint_path = checkpoint_path
        task.status = TaskStatus.FAILED
        task_service.save_task(task)
        activity_service.record_event(
            RunEvent(
                project_id=project.project_id,
                task_id=task.task_id,
                event_type="checkpoint.saved",
                message="Checkpoint saved for benchmark task.",
                payload={"checkpoint_path": checkpoint_path},
            )
        )
        task_service.retry_task(task.task_id)
        project_service.transition_flow(
            project.project_id,
            event=FlowEvent.RESUME,
            stage=project_service.get_flow_snapshot(project.project_id).stage,
            task_id=task.task_id,
            note="benchmark resume requested",
        )

        branch_runs = []
        for task_id, branch_name, accuracy in (
            ("bench-branch-a", "branch-a", 0.88),
            ("bench-branch-b", "branch-b", 0.91),
        ):
            task_service.create_task(
                Task(
                    task_id=task_id,
                    project_id=project.project_id,
                    kind="implement_experiment",
                    goal=f"Execute {branch_name}",
                    input_payload={"branch_name": branch_name},
                    owner="benchmark",
                    fanout_group=branch_name,
                )
            )
            run = run_service.register_run(
                RunManifest(
                    run_id=f"run-{task_id}",
                    spec_id="bench-spec",
                    git_commit="benchmark",
                    config_hash=f"cfg-{branch_name}",
                    dataset_snapshot="bench-dataset",
                    seed=1,
                    gpu="cpu",
                    status="completed",
                    experiment_branch=branch_name,
                    metrics={"accuracy": accuracy},
                )
            )
            branch_runs.append(run)

        flow = project_service.get_flow_snapshot(project.project_id)
        events = activity_service.list_events(project.project_id, limit=20)
        best_run = max(branch_runs, key=lambda item: float(item.metrics.get("accuracy", 0.0)))

        summary = {
            "project_id": project.project_id,
            "flow_stage": flow.stage.value,
            "flow_status": flow.status.value,
            "available_actions": list(available_flow_actions(flow)),
            "recent_event_count": len(events),
            "checkpoint_resume_available": checkpoint_path is not None,
            "branch_count": len(branch_runs),
            "best_branch": best_run.experiment_branch,
            "best_primary_metric": "accuracy",
            "best_primary_value": best_run.metrics.get("accuracy"),
        }
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
