from __future__ import annotations

from app.agents.orchestrator import Orchestrator
from app.core.paths import StorageBoundary
from app.providers.health import ProviderHealthService
from app.providers.registry import ProviderRegistry
from app.routing.models import DispatchProfile, ProviderSpec, ResolvedDispatch
from app.schemas.operator import ArtifactInspection, ProjectDashboard, RoutingInspection
from app.schemas.task import TaskStatus
from app.services.artifact_annotation_service import ArtifactAnnotationService
from app.services.artifact_service import ArtifactService
from app.services.freeze_service import FreezeService
from app.services.gap_map_service import GapMapService
from app.services.paper_card_service import PaperCardService
from app.services.project_service import ProjectService
from app.services.provenance_service import ProvenanceService
from app.services.run_service import RunService
from app.services.task_service import TaskService


class OperatorInspectionService:
    def __init__(
        self,
        *,
        project_service: ProjectService,
        task_service: TaskService,
        run_service: RunService,
        artifact_service: ArtifactService,
        artifact_annotation_service: ArtifactAnnotationService,
        paper_card_service: PaperCardService,
        gap_map_service: GapMapService,
        freeze_service: FreezeService,
        provenance_service: ProvenanceService,
        orchestrator: Orchestrator,
        provider_registry: ProviderRegistry,
        provider_health_service: ProviderHealthService,
        storage_boundary: StorageBoundary,
    ) -> None:
        self.project_service = project_service
        self.task_service = task_service
        self.run_service = run_service
        self.artifact_service = artifact_service
        self.artifact_annotation_service = artifact_annotation_service
        self.paper_card_service = paper_card_service
        self.gap_map_service = gap_map_service
        self.freeze_service = freeze_service
        self.provenance_service = provenance_service
        self.orchestrator = orchestrator
        self.provider_registry = provider_registry
        self.provider_health_service = provider_health_service
        self.storage_boundary = storage_boundary

    def build_project_dashboard(self, project_id: str) -> ProjectDashboard:
        project = self.project_service.get_project(project_id)
        if project is None:
            raise KeyError(f"Project not found: {project_id}")

        tasks = [task for task in self.task_service.list_tasks() if task.project_id == project_id]
        project_run_ids = {f"run-{task.task_id}" for task in tasks}
        artifacts = [artifact for artifact in self.artifact_service.list_artifacts() if artifact.run_id in project_run_ids]

        recommended_task_kind, recommendation_reason, expected_artifact, likely_next_task_kind = (
            self._recommend_next_task(tasks, project.description or project.name)
        )
        return ProjectDashboard(
            project_id=project.project_id,
            project_name=project.name,
            project_status=project.status,
            total_tasks=len(tasks),
            queued_tasks=sum(1 for task in tasks if task.status == TaskStatus.QUEUED),
            running_tasks=sum(1 for task in tasks if task.status == TaskStatus.RUNNING),
            waiting_approval_tasks=sum(1 for task in tasks if task.status == TaskStatus.WAITING_APPROVAL),
            succeeded_tasks=sum(1 for task in tasks if task.status == TaskStatus.SUCCEEDED),
            failed_tasks=sum(1 for task in tasks if task.status == TaskStatus.FAILED),
            cancelled_tasks=sum(1 for task in tasks if task.status == TaskStatus.CANCELLED),
            artifact_count=len(artifacts),
            paper_card_count=len(self.paper_card_service.list_cards()),
            gap_map_count=len(self.gap_map_service.list_gap_maps()),
            run_count=len([run for run in self.run_service.list_runs() if run.run_id in project_run_ids]),
            latest_task_ids=tuple(task.task_id for task in tasks[-5:]),
            topic_freeze_present=self.freeze_service.load_topic_freeze() is not None,
            spec_freeze_present=self.freeze_service.load_spec_freeze() is not None,
            results_freeze_present=self.freeze_service.load_results_freeze() is not None,
            recommended_next_task_kind=recommended_task_kind,
            recommendation_reason=recommendation_reason,
            expected_artifact=expected_artifact,
            likely_next_task_kind=likely_next_task_kind,
            storage_boundary=self.storage_boundary,
        )

    def inspect_system_routing(self) -> RoutingInspection:
        system_default = self.orchestrator.routing_resolver.system_default
        provider_name = (
            system_default.provider.provider_name
            if system_default.provider is not None
            else "local"
        )
        resolved = ResolvedDispatch(
            provider_name=provider_name,
            provider_family=provider_name,
            model=system_default.provider.model if system_default.provider is not None else None,
            model_profile_name=system_default.model_profile.profile_name
            if system_default.model_profile is not None
            else None,
            max_steps=system_default.max_steps,
            fallback_chain=[provider_name],
            decision_reason="system_default",
            sources={"provider_name": "system_default", "model": "system_default", "max_steps": "system_default"},
            metadata=dict(system_default.metadata),
        )
        return RoutingInspection(
            scope="system",
            subject_id=None,
            resolved_dispatch=resolved,
            provider_health=tuple(self.provider_health_service.list_snapshots(self.provider_registry)),
            storage_boundary=self.storage_boundary,
        )

    def inspect_task_routing(self, task_id: str) -> RoutingInspection:
        resolved = self.orchestrator.preview_routing(task_id)
        if resolved is None:
            task = self.task_service.get_task(task_id)
            if task is None:
                raise KeyError(f"Task not found: {task_id}")
            provider_name = (
                task.dispatch_profile.provider.provider_name
                if task.dispatch_profile is not None and task.dispatch_profile.provider is not None
                else self.orchestrator.routing_resolver.system_default.provider.provider_name
            )
            resolved = ResolvedDispatch(provider_name=provider_name, provider_family=provider_name)
        return RoutingInspection(
            scope="task",
            subject_id=task_id,
            resolved_dispatch=resolved,
            provider_health=tuple(self.provider_health_service.list_snapshots(self.provider_registry)),
            storage_boundary=self.storage_boundary,
        )

    def inspect_artifact(self, artifact_id: str) -> ArtifactInspection:
        artifact, provenance, annotations = self.provenance_service.build_artifact_provenance(artifact_id)
        return ArtifactInspection(
            artifact_id=artifact.artifact_id,
            run_id=artifact.run_id,
            kind=artifact.kind,
            path=artifact.path,
            exists_on_disk=provenance.exists_on_disk,
            verification_count=len(provenance.verification_links),
            audit_entry_count=len(provenance.audit_subject_refs),
            annotation_count=len(annotations),
            evidence_refs=tuple(
                sorted(
                    {
                        ref.raw_ref
                        for link in provenance.verification_links
                        for ref in link.evidence_refs
                    }
                    | {
                        ref.raw_ref
                        for audit_ref in provenance.audit_subject_refs
                        for ref in audit_ref.evidence_refs
                    }
                )
            ),
            claim_supports=tuple(
                f"{ref.claim_id}:{ref.support_kind}:{ref.support_value}"
                for ref in provenance.claim_support_refs
            ),
            related_freeze_ids=tuple(ref.subject_id for ref in provenance.freeze_subject_refs),
            metadata=dict(artifact.metadata),
            resolved_path=provenance.resolved_path,
            workspace_relative_path=provenance.workspace_relative_path,
        )

    def list_provider_health(self):
        return self.provider_health_service.list_snapshots(self.provider_registry)

    def disable_provider_family(self, provider_name: str):
        self.provider_health_service.disable_family(provider_name)
        return self.provider_health_service.snapshot(provider_name, self.provider_registry)

    def enable_provider_family(self, provider_name: str):
        self.provider_health_service.enable_family(provider_name)
        return self.provider_health_service.snapshot(provider_name, self.provider_registry)

    def clear_provider_cooldown(self, provider_name: str):
        self.provider_health_service.clear_cooldown(provider_name)
        return self.provider_health_service.snapshot(provider_name, self.provider_registry)

    async def probe_provider_family(self, provider_name: str):
        return await self.provider_health_service.probe_provider(provider_name, self.provider_registry)

    @staticmethod
    def _recommend_next_task(tasks, fallback_goal: str) -> tuple[str | None, str, str, str | None]:
        completed_kinds = {
            task.kind
            for task in tasks
            if task.status in {TaskStatus.SUCCEEDED, TaskStatus.RUNNING, TaskStatus.WAITING_APPROVAL}
        }
        if not tasks:
            return (
                "paper_ingest",
                f"Start with one bounded ingestion task for {fallback_goal} so the project gets its first durable evidence.",
                "paper_card",
                "gap_mapping",
            )
        if not completed_kinds.intersection({"paper_ingest", "repo_ingest", "read_source"}):
            return (
                "paper_ingest",
                "No completed source-ingestion task exists yet.",
                "paper_card",
                "gap_mapping",
            )
        if not completed_kinds.intersection({"gap_mapping", "map_gaps"}):
            return (
                "gap_mapping",
                "The project has source evidence but no gap map yet.",
                "gap_map",
                "build_spec",
            )
        if not completed_kinds.intersection({"build_spec", "implement_experiment", "reproduce_baseline"}):
            return (
                "build_spec",
                "The project has evidence and synthesis, but no experiment plan yet.",
                "hypothesis_set / experiment_spec",
                "implement_experiment",
            )
        if not completed_kinds.intersection({"review_build", "audit_run", "verify_evidence", "verify_results"}):
            return (
                "audit_run",
                "Execution work exists, but review and verification are still missing.",
                "review_report",
                "write_draft",
            )
        if not completed_kinds.intersection({"write_draft", "write_section"}):
            return (
                "write_draft",
                "The project already has executable outputs. The next step is to turn them into a draft.",
                "paper_draft",
                "style_pass",
            )
        return (
            "archive_research",
            "The core loop is populated. Archive lessons and provenance before starting the next cycle.",
            "archive_entry",
            None,
        )
