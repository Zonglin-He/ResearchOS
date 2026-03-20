from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from app.routing.models import DispatchProfile
from app.schemas.approval import Approval
from app.schemas.gap_map import GapMap
from app.schemas.project import Project
from app.schemas.task import Task
from app.services.approval_service import ApprovalService
from app.services.artifact_service import ArtifactService
from app.services.claim_service import ClaimService
from app.services.freeze_service import FreezeService
from app.services.gap_map_service import GapMapService
from app.services.paper_card_service import PaperCardService
from app.services.project_service import ProjectService
from app.services.run_service import RunService
from app.services.task_service import TaskService
from app.worker.tasks import dispatch_task as dispatch_task_job


@dataclass
class ProjectCreateInput:
    project_id: str
    name: str
    description: str
    status: str = "active"
    dispatch_profile: DispatchProfile | None = None


@dataclass
class TaskCreateInput:
    task_id: str
    project_id: str
    kind: str
    goal: str
    owner: str
    input_payload: dict[str, Any]
    assigned_agent: str | None = None
    parent_task_id: str | None = None
    dispatch_profile: DispatchProfile | None = None


@dataclass
class ApprovalCreateInput:
    approval_id: str
    project_id: str
    target_type: str
    target_id: str
    approved_by: str
    decision: str
    comment: str = ""


class ConsoleControlPlane:
    def __init__(
        self,
        *,
        project_service: ProjectService,
        task_service: TaskService,
        approval_service: ApprovalService,
        run_service: RunService,
        artifact_service: ArtifactService,
        claim_service: ClaimService,
        paper_card_service: PaperCardService,
        gap_map_service: GapMapService,
        freeze_service: FreezeService,
        orchestrator,
        routing_resolver,
        provider_registry,
        provider_invocation_service=None,
    ) -> None:
        self.project_service = project_service
        self.task_service = task_service
        self.approval_service = approval_service
        self.run_service = run_service
        self.artifact_service = artifact_service
        self.claim_service = claim_service
        self.paper_card_service = paper_card_service
        self.gap_map_service = gap_map_service
        self.freeze_service = freeze_service
        self.orchestrator = orchestrator
        self.routing_resolver = routing_resolver
        self.provider_registry = provider_registry
        self.provider_invocation_service = provider_invocation_service

    @classmethod
    def from_runtime_services(cls, services) -> "ConsoleControlPlane":
        return cls(
            project_service=services.project_service,
            task_service=services.task_service,
            approval_service=services.approval_service,
            run_service=services.run_service,
            artifact_service=services.artifact_service,
            claim_service=services.claim_service,
            paper_card_service=services.paper_card_service,
            gap_map_service=services.gap_map_service,
            freeze_service=services.freeze_service,
            orchestrator=services.orchestrator,
            routing_resolver=services.routing_resolver,
            provider_registry=services.provider_registry,
            provider_invocation_service=services.provider_invocation_service,
        )

    def system_dispatch_profile(self) -> DispatchProfile:
        return self.routing_resolver.system_default

    def has_projects(self) -> bool:
        return bool(self.project_service.list_projects())

    def provider_names(self) -> list[str]:
        return self.provider_registry.list_names()

    def create_project(self, data: ProjectCreateInput) -> Project:
        return self.project_service.create_project(
            Project(
                project_id=data.project_id,
                name=data.name,
                description=data.description,
                status=data.status,
                dispatch_profile=data.dispatch_profile,
            )
        )

    def list_projects(self) -> list[Project]:
        return self.project_service.list_projects()

    def create_task(self, data: TaskCreateInput) -> Task:
        return self.task_service.create_task(
            Task(
                task_id=data.task_id,
                project_id=data.project_id,
                kind=data.kind,
                goal=data.goal,
                input_payload=data.input_payload,
                owner=data.owner,
                assigned_agent=data.assigned_agent,
                parent_task_id=data.parent_task_id,
                dispatch_profile=data.dispatch_profile,
            )
        )

    def list_tasks(self, project_id: str | None = None) -> list[Task]:
        tasks = self.task_service.list_tasks()
        if project_id is not None:
            tasks = [task for task in tasks if task.project_id == project_id]
        return tasks

    def dispatch_task(self, task_id: str, *, run_async: bool = False):
        if run_async:
            return dispatch_task_job.delay(task_id)
        return asyncio.run(self.orchestrator.dispatch(task_id))

    def create_approval(self, data: ApprovalCreateInput) -> Approval:
        return self.approval_service.record_approval(
            Approval(
                approval_id=data.approval_id,
                project_id=data.project_id,
                target_type=data.target_type,
                target_id=data.target_id,
                approved_by=data.approved_by,
                decision=data.decision,
                comment=data.comment,
            )
        )

    def list_approvals(self, *, pending_only: bool = False) -> list[Approval]:
        if pending_only:
            return self.approval_service.list_pending()
        return self.approval_service.list_approvals()

    def list_runs(self):
        return self.run_service.list_runs()

    def list_artifacts(self):
        return self.artifact_service.list_artifacts()

    def list_claims(self):
        return self.claim_service.list_claims()

    def list_paper_cards(self):
        return self.paper_card_service.list_cards()

    def list_gap_maps(self) -> list[GapMap]:
        return self.gap_map_service.list_gap_maps()

    def get_topic_freeze(self):
        return self.freeze_service.load_topic_freeze()

    def get_spec_freeze(self):
        return self.freeze_service.load_spec_freeze()

    def get_results_freeze(self):
        return self.freeze_service.load_results_freeze()

    @staticmethod
    def build_task_input_payload(
        *,
        kind: str,
        topic: str = "",
        source_title: str = "",
        source_abstract: str = "",
        source_setting: str = "",
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if topic:
            payload["topic"] = topic
        if kind in {"paper_ingest", "repo_ingest", "read_source"} and any(
            [source_title, source_abstract, source_setting]
        ):
            payload["source_summary"] = {
                "title": source_title,
                "abstract": source_abstract,
                "setting": source_setting,
            }
        return payload
