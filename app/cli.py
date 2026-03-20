from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

from app.bootstrap import build_runtime_services
from app.console.app import TerminalControlPlaneApp
from app.console.control_plane import ConsoleControlPlane
from app.core.config import load_config
from app.routing import dispatch_profile_from_dict
from app.schemas.claim import Claim
from app.schemas.gap_map import Gap, GapCluster, GapMap
from app.schemas.freeze import ResultsFreeze, SpecFreeze, TopicFreeze
from app.schemas.lesson import LessonKind, LessonRecord
from app.schemas.paper_card import EvidenceRef, PaperCard
from app.schemas.project import Project
from app.schemas.run_manifest import RunManifest
from app.schemas.task import Task, TaskStatus
from app.services.project_service import ProjectService
from app.services.registry_store import to_record
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

    console = subparsers.add_parser("console")
    console.add_argument("--refresh-interval", type=float, default=2.0)
    console.set_defaults(handler=_handle_console)

    create_project = subparsers.add_parser("create-project")
    create_project.add_argument("--project-id", required=True)
    create_project.add_argument("--name", required=True)
    create_project.add_argument("--description", required=True)
    create_project.add_argument("--status", default="active")
    create_project.add_argument("--dispatch-profile")
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
    create_task.add_argument("--dispatch-profile")
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

    create_lesson = subparsers.add_parser("create-lesson")
    create_lesson.add_argument("--lesson-id", required=True)
    create_lesson.add_argument("--lesson-kind", required=True, choices=[kind.value for kind in LessonKind])
    create_lesson.add_argument("--title", required=True)
    create_lesson.add_argument("--summary", required=True)
    create_lesson.add_argument("--rationale", default="")
    create_lesson.add_argument("--recommended-action", default="")
    create_lesson.add_argument("--task-kind")
    create_lesson.add_argument("--agent-name")
    create_lesson.add_argument("--tool-name")
    create_lesson.add_argument("--provider-name")
    create_lesson.add_argument("--model-name")
    create_lesson.add_argument("--failure-type")
    create_lesson.add_argument("--repository-ref")
    create_lesson.add_argument("--dataset-ref")
    create_lesson.add_argument("--context-tag", action="append", dest="context_tags", default=[])
    create_lesson.add_argument("--evidence-ref", action="append", dest="evidence_refs", default=[])
    create_lesson.add_argument("--artifact-id", action="append", dest="artifact_ids", default=[])
    create_lesson.add_argument("--source-task-id")
    create_lesson.add_argument("--source-run-id")
    create_lesson.add_argument("--source-claim-id")
    create_lesson.set_defaults(handler=_handle_create_lesson)

    list_lessons = subparsers.add_parser("list-lessons")
    list_lessons.add_argument("--task-kind")
    list_lessons.add_argument("--agent-name")
    list_lessons.add_argument("--tool-name")
    list_lessons.add_argument("--provider-name")
    list_lessons.add_argument("--model-name")
    list_lessons.add_argument("--failure-type")
    list_lessons.add_argument("--repository-ref")
    list_lessons.add_argument("--dataset-ref")
    list_lessons.add_argument("--lesson-kind", choices=[kind.value for kind in LessonKind])
    list_lessons.set_defaults(handler=_handle_list_lessons)

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

    verify_run = subparsers.add_parser("verify-run")
    verify_run.add_argument("--run-id", required=True)
    verify_run.set_defaults(handler=_handle_verify_run)

    verify_claim = subparsers.add_parser("verify-claim")
    verify_claim.add_argument("--claim-id", required=True)
    verify_claim.set_defaults(handler=_handle_verify_claim)

    verify_results_freeze = subparsers.add_parser("verify-results-freeze")
    verify_results_freeze.set_defaults(handler=_handle_verify_results_freeze)

    list_verifications = subparsers.add_parser("list-verifications")
    list_verifications.add_argument("--subject-type")
    list_verifications.add_argument("--subject-id")
    list_verifications.add_argument("--check-type")
    list_verifications.add_argument("--status")
    list_verifications.set_defaults(handler=_handle_list_verifications)

    audit_claims = subparsers.add_parser("audit-claims")
    audit_claims.set_defaults(handler=_handle_audit_claims)

    audit_run = subparsers.add_parser("audit-run")
    audit_run.add_argument("--run-id", required=True)
    audit_run.set_defaults(handler=_handle_audit_run)

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

    list_artifacts = subparsers.add_parser("list-artifacts")
    list_artifacts.add_argument("--run-id")
    list_artifacts.set_defaults(handler=_handle_list_artifacts)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config()
    config.db_path = args.db_path
    services = build_runtime_services(config)
    args.runtime_services = services
    args.runtime_config = config
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


def _handle_console(
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
    control_plane = ConsoleControlPlane.from_runtime_services(args.runtime_services)
    app = TerminalControlPlaneApp(control_plane, refresh_interval=args.refresh_interval)
    return app.run()


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
        dispatch_profile=_load_dispatch_profile_arg(args.dispatch_profile),
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
        dispatch_profile=_load_dispatch_profile_arg(args.dispatch_profile),
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
    if dispatch.result.routing is not None:
        print(
            "Routing "
            f"provider={dispatch.result.routing.provider_name} "
            f"model={dispatch.result.routing.model or '<default>'} "
            f"sources={to_record(dispatch.result.routing.sources)}"
        )
    return 0


def _load_dispatch_profile_arg(raw_value: str | None):
    if raw_value is None:
        return None
    return dispatch_profile_from_dict(json.loads(raw_value))


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


def _handle_create_lesson(
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
    lesson = LessonRecord(
        lesson_id=args.lesson_id,
        lesson_kind=LessonKind(args.lesson_kind),
        title=args.title,
        summary=args.summary,
        rationale=args.rationale,
        recommended_action=args.recommended_action,
        task_kind=args.task_kind,
        agent_name=args.agent_name,
        tool_name=args.tool_name,
        provider_name=args.provider_name,
        model_name=args.model_name,
        failure_type=args.failure_type,
        repository_ref=args.repository_ref,
        dataset_ref=args.dataset_ref,
        context_tags=args.context_tags,
        evidence_refs=args.evidence_refs,
        artifact_ids=args.artifact_ids,
        source_task_id=args.source_task_id,
        source_run_id=args.source_run_id,
        source_claim_id=args.source_claim_id,
    )
    args.runtime_services.lessons_service.record_lesson(lesson)
    print(f"Created lesson {lesson.lesson_id}")
    return 0


def _handle_list_lessons(
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
    lessons = args.runtime_services.lessons_service.list_lessons(
        task_kind=args.task_kind,
        agent_name=args.agent_name,
        tool_name=args.tool_name,
        provider_name=args.provider_name,
        model_name=args.model_name,
        failure_type=args.failure_type,
        repository_ref=args.repository_ref,
        dataset_ref=args.dataset_ref,
        lesson_kind=LessonKind(args.lesson_kind) if args.lesson_kind else None,
    )
    for lesson in lessons:
        print(
            f"{lesson.lesson_id}\t{lesson.lesson_kind.value}\t"
            f"{lesson.task_kind or '-'}\t{lesson.agent_name or '-'}\t{lesson.title}"
        )
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


def _handle_verify_run(
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
    record = args.runtime_services.verification_service.verify_run_manifest(args.run_id)
    print(f"{record.subject_type}:{record.subject_id}\t{record.check_type.value}\t{record.status.value}")
    if record.missing_fields:
        print(f"missing={','.join(record.missing_fields)}")
    print(record.rationale)
    return 0


def _handle_verify_claim(
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
    record = args.runtime_services.verification_service.verify_claim_evidence(args.claim_id)
    print(f"{record.subject_type}:{record.subject_id}\t{record.check_type.value}\t{record.status.value}")
    if record.missing_fields:
        print(f"missing={','.join(record.missing_fields)}")
    print(record.rationale)
    return 0


def _handle_verify_results_freeze(
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
    record = args.runtime_services.verification_service.verify_results_freeze()
    print(f"{record.subject_type}:{record.subject_id}\t{record.check_type.value}\t{record.status.value}")
    if record.missing_fields:
        print(f"missing={','.join(record.missing_fields)}")
    print(record.rationale)
    return 0


def _handle_list_verifications(
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
    records = args.runtime_services.verification_service.list_checks(
        subject_type=args.subject_type,
        subject_id=args.subject_id,
        check_type=args.check_type,
        status=args.status,
    )
    for record in records:
        print(
            f"{record.verification_id}\t{record.subject_type}\t{record.subject_id}\t"
            f"{record.check_type.value}\t{record.status.value}"
        )
    return 0


def _handle_audit_claims(
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
    report = args.runtime_services.audit_service.build_claim_alignment_report()
    print(f"{report.report_type}\t{report.status}")
    for entry in report.entries:
        print(f"{entry.category}\t{entry.status}\t{entry.subject_id}\t{entry.rationale}")
    return 0


def _handle_audit_run(
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
    report = args.runtime_services.audit_service.build_run_verification_report(
        args.run_id,
        args.runtime_services.verification_service,
    )
    print(f"{report.report_type}\t{report.status}")
    for entry in report.entries:
        print(f"{entry.category}\t{entry.status}\t{entry.subject_id}\t{entry.rationale}")
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


def _handle_list_artifacts(
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
    artifacts = args.runtime_services.artifact_service.list_artifacts()
    if args.run_id:
        artifacts = [artifact for artifact in artifacts if artifact.run_id == args.run_id]
    for artifact in artifacts:
        print(f"{artifact.artifact_id}\t{artifact.run_id}\t{artifact.kind}\t{artifact.path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
