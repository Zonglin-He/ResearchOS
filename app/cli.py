from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.bootstrap import build_runtime_services
from app.core.config import load_config
from app.schemas.claim import Claim
from app.schemas.gap_map import Gap, GapCluster, GapMap
from app.schemas.freeze import ResultsFreeze, SpecFreeze, TopicFreeze
from app.schemas.paper_card import EvidenceRef, PaperCard
from app.schemas.project import Project
from app.schemas.run_manifest import RunManifest
from app.schemas.task import Task, TaskStatus
from app.services.project_service import ProjectService
from app.services.task_service import TaskService
from app.worker.tasks import dispatch_task as dispatch_task_job


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="researchos")
    parser.add_argument(
        "--db-path",
        default=str(Path("data") / "researchos.db"),
        help="SQLite database path",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_db = subparsers.add_parser("init-db")
    init_db.set_defaults(handler=_handle_init_db)

    create_project = subparsers.add_parser("create-project")
    create_project.add_argument("--project-id", required=True)
    create_project.add_argument("--name", required=True)
    create_project.add_argument("--description", required=True)
    create_project.add_argument("--status", default="active")
    create_project.set_defaults(handler=_handle_create_project)

    list_projects = subparsers.add_parser("list-projects")
    list_projects.set_defaults(handler=_handle_list_projects)

    create_task = subparsers.add_parser("create-task")
    create_task.add_argument("--task-id", required=True)
    create_task.add_argument("--project-id", required=True)
    create_task.add_argument("--kind", required=True)
    create_task.add_argument("--goal", required=True)
    create_task.add_argument("--owner", required=True)
    create_task.add_argument("--input-payload", default="{}")
    create_task.add_argument("--assigned-agent")
    create_task.add_argument("--parent-task-id")
    create_task.set_defaults(handler=_handle_create_task)

    list_tasks = subparsers.add_parser("list-tasks")
    list_tasks.add_argument("--project-id")
    list_tasks.set_defaults(handler=_handle_list_tasks)

    update_status = subparsers.add_parser("update-task-status")
    update_status.add_argument("--task-id", required=True)
    update_status.add_argument("--status", required=True, choices=[status.value for status in TaskStatus])
    update_status.set_defaults(handler=_handle_update_task_status)

    retry_task = subparsers.add_parser("retry-task")
    retry_task.add_argument("--task-id", required=True)
    retry_task.set_defaults(handler=_handle_retry_task)

    cancel_task = subparsers.add_parser("cancel-task")
    cancel_task.add_argument("--task-id", required=True)
    cancel_task.set_defaults(handler=_handle_cancel_task)

    dispatch_task = subparsers.add_parser("dispatch-task")
    dispatch_task.add_argument("--task-id", required=True)
    dispatch_task.add_argument(
        "--async",
        action="store_true",
        dest="run_async",
        help="Enqueue through Celery instead of dispatching inline.",
    )
    dispatch_task.set_defaults(handler=_handle_dispatch_task)

    create_claim = subparsers.add_parser("create-claim")
    create_claim.add_argument("--claim-id", required=True)
    create_claim.add_argument("--text", required=True)
    create_claim.add_argument("--claim-type", required=True)
    create_claim.add_argument("--risk-level", default="medium")
    create_claim.set_defaults(handler=_handle_create_claim)

    list_claims = subparsers.add_parser("list-claims")
    list_claims.set_defaults(handler=_handle_list_claims)

    create_run = subparsers.add_parser("create-run")
    create_run.add_argument("--run-id", required=True)
    create_run.add_argument("--spec-id", required=True)
    create_run.add_argument("--git-commit", required=True)
    create_run.add_argument("--config-hash", required=True)
    create_run.add_argument("--dataset-snapshot", required=True)
    create_run.add_argument("--seed", type=int, required=True)
    create_run.add_argument("--gpu", required=True)
    create_run.set_defaults(handler=_handle_create_run)

    list_runs = subparsers.add_parser("list-runs")
    list_runs.set_defaults(handler=_handle_list_runs)

    save_topic_freeze = subparsers.add_parser("save-topic-freeze")
    save_topic_freeze.add_argument("--topic-id", required=True)
    save_topic_freeze.add_argument("--research-question", required=True)
    save_topic_freeze.add_argument("--owner", required=True)
    save_topic_freeze.add_argument("--selected-gap-id", action="append", dest="selected_gap_ids", default=[])
    save_topic_freeze.add_argument("--novelty-type", action="append", dest="novelty_type", default=[])
    save_topic_freeze.set_defaults(handler=_handle_save_topic_freeze)

    save_spec_freeze = subparsers.add_parser("save-spec-freeze")
    save_spec_freeze.add_argument("--spec-id", required=True)
    save_spec_freeze.add_argument("--topic-id", required=True)
    save_spec_freeze.add_argument("--hypothesis", action="append", default=[])
    save_spec_freeze.add_argument("--baseline", action="append", dest="must_beat_baselines", default=[])
    save_spec_freeze.set_defaults(handler=_handle_save_spec_freeze)

    save_results_freeze = subparsers.add_parser("save-results-freeze")
    save_results_freeze.add_argument("--results-id", required=True)
    save_results_freeze.add_argument("--spec-id", required=True)
    save_results_freeze.add_argument("--claim-id", action="append", dest="main_claims", default=[])
    save_results_freeze.add_argument("--table", action="append", dest="tables", default=[])
    save_results_freeze.add_argument("--figure", action="append", dest="figures", default=[])
    save_results_freeze.set_defaults(handler=_handle_save_results_freeze)

    create_paper_card = subparsers.add_parser("create-paper-card")
    create_paper_card.add_argument("--paper-id", required=True)
    create_paper_card.add_argument("--title", required=True)
    create_paper_card.add_argument("--problem", required=True)
    create_paper_card.add_argument("--setting", required=True)
    create_paper_card.add_argument("--task-type", required=True)
    create_paper_card.set_defaults(handler=_handle_create_paper_card)

    list_paper_cards = subparsers.add_parser("list-paper-cards")
    list_paper_cards.set_defaults(handler=_handle_list_paper_cards)

    create_gap_map = subparsers.add_parser("create-gap-map")
    create_gap_map.add_argument("--topic", required=True)
    create_gap_map.add_argument("--cluster-name", required=True)
    create_gap_map.add_argument("--gap-id", required=True)
    create_gap_map.add_argument("--description", required=True)
    create_gap_map.set_defaults(handler=_handle_create_gap_map)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config()
    config.db_path = args.db_path
    services = build_runtime_services(config)
    return args.handler(
        args,
        services.project_service,
        services.task_service,
        services.claim_service,
        services.run_service,
        services.freeze_service,
        services.paper_card_service,
        services.gap_map_service,
        services.approval_service,
    )


def _handle_init_db(
    args: argparse.Namespace,
    project_service: ProjectService,
    task_service: TaskService,
    claim_service: ClaimService,
    run_service: RunService,
    freeze_service: FreezeService,
    paper_card_service: PaperCardService,
    gap_map_service: GapMapService,
    approval_service: ApprovalService,
) -> int:
    print(f"Initialized database at {args.db_path}")
    return 0


def _handle_create_project(
    args: argparse.Namespace,
    project_service: ProjectService,
    task_service: TaskService,
    claim_service: ClaimService,
    run_service: RunService,
    freeze_service: FreezeService,
    paper_card_service: PaperCardService,
    gap_map_service: GapMapService,
    approval_service: ApprovalService,
) -> int:
    project = Project(
        project_id=args.project_id,
        name=args.name,
        description=args.description,
        status=args.status,
    )
    project_service.create_project(project)
    print(f"Created project {project.project_id}")
    return 0


def _handle_list_projects(
    args: argparse.Namespace,
    project_service: ProjectService,
    task_service: TaskService,
    claim_service: ClaimService,
    run_service: RunService,
    freeze_service: FreezeService,
    paper_card_service: PaperCardService,
    gap_map_service: GapMapService,
    approval_service: ApprovalService,
) -> int:
    projects = project_service.list_projects()
    for project in projects:
        print(f"{project.project_id}\t{project.name}\t{project.status}")
    return 0


def _handle_create_task(
    args: argparse.Namespace,
    project_service: ProjectService,
    task_service: TaskService,
    claim_service: ClaimService,
    run_service: RunService,
    freeze_service: FreezeService,
    paper_card_service: PaperCardService,
    gap_map_service: GapMapService,
    approval_service: ApprovalService,
) -> int:
    payload = json.loads(args.input_payload)
    task = Task(
        task_id=args.task_id,
        project_id=args.project_id,
        kind=args.kind,
        goal=args.goal,
        input_payload=payload,
        owner=args.owner,
        assigned_agent=args.assigned_agent,
        parent_task_id=args.parent_task_id,
    )
    task_service.create_task(task)
    print(f"Created task {task.task_id}")
    return 0


def _handle_list_tasks(
    args: argparse.Namespace,
    project_service: ProjectService,
    task_service: TaskService,
    claim_service: ClaimService,
    run_service: RunService,
    freeze_service: FreezeService,
    paper_card_service: PaperCardService,
    gap_map_service: GapMapService,
    approval_service: ApprovalService,
) -> int:
    tasks = task_service.list_tasks()
    if args.project_id:
        tasks = [task for task in tasks if task.project_id == args.project_id]
    for task in tasks:
        print(f"{task.task_id}\t{task.project_id}\t{task.kind}\t{task.status.value}")
    return 0


def _handle_update_task_status(
    args: argparse.Namespace,
    project_service: ProjectService,
    task_service: TaskService,
    claim_service: ClaimService,
    run_service: RunService,
    freeze_service: FreezeService,
    paper_card_service: PaperCardService,
    gap_map_service: GapMapService,
    approval_service: ApprovalService,
) -> int:
    task = task_service.update_status(args.task_id, TaskStatus(args.status))
    print(f"Updated task {task.task_id} to {task.status.value}")
    return 0


def _handle_retry_task(
    args: argparse.Namespace,
    project_service: ProjectService,
    task_service: TaskService,
    claim_service: ClaimService,
    run_service: RunService,
    freeze_service: FreezeService,
    paper_card_service: PaperCardService,
    gap_map_service: GapMapService,
    approval_service: ApprovalService,
) -> int:
    task = task_service.retry_task(args.task_id)
    print(f"Retried task {task.task_id} -> {task.status.value}")
    return 0


def _handle_cancel_task(
    args: argparse.Namespace,
    project_service: ProjectService,
    task_service: TaskService,
    claim_service: ClaimService,
    run_service: RunService,
    freeze_service: FreezeService,
    paper_card_service: PaperCardService,
    gap_map_service: GapMapService,
    approval_service: ApprovalService,
) -> int:
    task = task_service.cancel_task(args.task_id)
    print(f"Cancelled task {task.task_id}")
    return 0


def _handle_dispatch_task(
    args: argparse.Namespace,
    project_service: ProjectService,
    task_service: TaskService,
    claim_service: ClaimService,
    run_service: RunService,
    freeze_service: FreezeService,
    paper_card_service: PaperCardService,
    gap_map_service: GapMapService,
    approval_service: ApprovalService,
) -> int:
    if args.run_async:
        result = dispatch_task_job.delay(args.task_id)
        print(f"Enqueued task {args.task_id} as Celery job {result.id}")
        return 0

    config = load_config()
    config.db_path = args.db_path
    services = build_runtime_services(config)
    dispatch = asyncio.run(services.orchestrator.dispatch(args.task_id))
    print(
        f"Dispatched task {dispatch.task.task_id} -> "
        f"{dispatch.task.status.value} ({dispatch.result.status})"
    )
    return 0


def _handle_create_claim(
    args: argparse.Namespace,
    project_service: ProjectService,
    task_service: TaskService,
    claim_service: ClaimService,
    run_service: RunService,
    freeze_service: FreezeService,
    paper_card_service: PaperCardService,
    gap_map_service: GapMapService,
    approval_service: ApprovalService,
) -> int:
    claim = Claim(
        claim_id=args.claim_id,
        text=args.text,
        claim_type=args.claim_type,
        risk_level=args.risk_level,
    )
    claim_service.register_claim(claim)
    print(f"Created claim {claim.claim_id}")
    return 0


def _handle_list_claims(
    args: argparse.Namespace,
    project_service: ProjectService,
    task_service: TaskService,
    claim_service: ClaimService,
    run_service: RunService,
    freeze_service: FreezeService,
    paper_card_service: PaperCardService,
    gap_map_service: GapMapService,
    approval_service: ApprovalService,
) -> int:
    for claim in claim_service.list_claims():
        print(f"{claim.claim_id}\t{claim.claim_type}\t{claim.risk_level}")
    return 0


def _handle_create_run(
    args: argparse.Namespace,
    project_service: ProjectService,
    task_service: TaskService,
    claim_service: ClaimService,
    run_service: RunService,
    freeze_service: FreezeService,
    paper_card_service: PaperCardService,
    gap_map_service: GapMapService,
    approval_service: ApprovalService,
) -> int:
    run = RunManifest(
        run_id=args.run_id,
        spec_id=args.spec_id,
        git_commit=args.git_commit,
        config_hash=args.config_hash,
        dataset_snapshot=args.dataset_snapshot,
        seed=args.seed,
        gpu=args.gpu,
    )
    run_service.register_run(run)
    print(f"Created run {run.run_id}")
    return 0


def _handle_list_runs(
    args: argparse.Namespace,
    project_service: ProjectService,
    task_service: TaskService,
    claim_service: ClaimService,
    run_service: RunService,
    freeze_service: FreezeService,
    paper_card_service: PaperCardService,
    gap_map_service: GapMapService,
    approval_service: ApprovalService,
) -> int:
    for run in run_service.list_runs():
        print(f"{run.run_id}\t{run.spec_id}\t{run.status}")
    return 0


def _handle_save_topic_freeze(
    args: argparse.Namespace,
    project_service: ProjectService,
    task_service: TaskService,
    claim_service: ClaimService,
    run_service: RunService,
    freeze_service: FreezeService,
    paper_card_service: PaperCardService,
    gap_map_service: GapMapService,
    approval_service: ApprovalService,
) -> int:
    freeze_service.save_topic_freeze(
        TopicFreeze(
            topic_id=args.topic_id,
            selected_gap_ids=args.selected_gap_ids,
            research_question=args.research_question,
            novelty_type=args.novelty_type,
            owner=args.owner,
        )
    )
    print(f"Saved topic freeze {args.topic_id}")
    return 0


def _handle_save_spec_freeze(
    args: argparse.Namespace,
    project_service: ProjectService,
    task_service: TaskService,
    claim_service: ClaimService,
    run_service: RunService,
    freeze_service: FreezeService,
) -> int:
    freeze_service.save_spec_freeze(
        SpecFreeze(
            spec_id=args.spec_id,
            topic_id=args.topic_id,
            hypothesis=args.hypothesis,
            must_beat_baselines=args.must_beat_baselines,
        )
    )
    print(f"Saved spec freeze {args.spec_id}")
    return 0


def _handle_save_results_freeze(
    args: argparse.Namespace,
    project_service: ProjectService,
    task_service: TaskService,
    claim_service: ClaimService,
    run_service: RunService,
    freeze_service: FreezeService,
    paper_card_service: PaperCardService,
    gap_map_service: GapMapService,
    approval_service: ApprovalService,
) -> int:
    freeze_service.save_results_freeze(
        ResultsFreeze(
            results_id=args.results_id,
            spec_id=args.spec_id,
            main_claims=args.main_claims,
            tables=args.tables,
            figures=args.figures,
        )
    )
    print(f"Saved results freeze {args.results_id}")
    return 0


def _handle_create_paper_card(
    args: argparse.Namespace,
    project_service: ProjectService,
    task_service: TaskService,
    claim_service: ClaimService,
    run_service: RunService,
    freeze_service: FreezeService,
    paper_card_service: PaperCardService,
    gap_map_service: GapMapService,
    approval_service: ApprovalService,
) -> int:
    card = PaperCard(
        paper_id=args.paper_id,
        title=args.title,
        problem=args.problem,
        setting=args.setting,
        task_type=args.task_type,
        evidence_refs=[EvidenceRef(section="manual", page=1)],
    )
    paper_card_service.register_card(card)
    print(f"Created paper card {card.paper_id}")
    return 0


def _handle_list_paper_cards(
    args: argparse.Namespace,
    project_service: ProjectService,
    task_service: TaskService,
    claim_service: ClaimService,
    run_service: RunService,
    freeze_service: FreezeService,
    paper_card_service: PaperCardService,
    gap_map_service: GapMapService,
    approval_service: ApprovalService,
) -> int:
    for card in paper_card_service.list_cards():
        print(f"{card.paper_id}\t{card.title}\t{card.task_type}")
    return 0


def _handle_create_gap_map(
    args: argparse.Namespace,
    project_service: ProjectService,
    task_service: TaskService,
    claim_service: ClaimService,
    run_service: RunService,
    freeze_service: FreezeService,
    paper_card_service: PaperCardService,
    gap_map_service: GapMapService,
    approval_service: ApprovalService,
) -> int:
    gap_map = GapMap(
        topic=args.topic,
        clusters=[
            GapCluster(
                name=args.cluster_name,
                gaps=[Gap(gap_id=args.gap_id, description=args.description)],
            )
        ],
    )
    gap_map_service.register_gap_map(gap_map)
    print(f"Created gap map for topic {gap_map.topic}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
