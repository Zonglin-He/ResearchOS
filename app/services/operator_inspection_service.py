from __future__ import annotations

from app.agents.orchestrator import Orchestrator
from app.core.paths import StorageBoundary
from app.providers.health import ProviderHealthService
from app.providers.registry import ProviderRegistry
from app.routing.models import DispatchProfile, ProviderSpec, ResolvedDispatch
from app.schemas.operator import (
    ArtifactInspection,
    BranchComparison,
    BranchRunSummary,
    ProjectDashboard,
    RoutingInspection,
)
from app.schemas.task import TaskStatus
from app.services.artifact_annotation_service import ArtifactAnnotationService
from app.services.artifact_service import ArtifactService
from app.services.freeze_service import FreezeService
from app.services.gap_map_service import GapMapService
from app.services.memory_registry_service import MemoryRegistryService
from app.services.paper_card_service import PaperCardService
from app.services.project_service import ProjectService
from app.services.provenance_service import ProvenanceService
from app.services.run_service import RunService
from app.services.strategy_service import StrategyService
from app.services.task_service import TaskService
from app.workflows.research_flow import available_flow_actions


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
        strategy_service: StrategyService,
        memory_registry_service: MemoryRegistryService,
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
        self.strategy_service = strategy_service
        self.memory_registry_service = memory_registry_service
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
        flow_snapshot = self.project_service.get_flow_snapshot(project_id)
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
            flow_snapshot=flow_snapshot,
            available_flow_actions=available_flow_actions(flow_snapshot),
            storage_boundary=self.storage_boundary,
        )

    def inspect_project_flow(self, project_id: str):
        project = self.project_service.get_project(project_id)
        if project is None:
            raise KeyError(f"Project not found: {project_id}")
        return self.project_service.get_flow_snapshot(project_id)

    def compare_project_branches(self, project_id: str) -> BranchComparison:
        project = self.project_service.get_project(project_id)
        if project is None:
            raise KeyError(f"Project not found: {project_id}")
        tasks = [task for task in self.task_service.list_tasks() if task.project_id == project_id]
        runs = [run for run in self.run_service.list_runs() if self._run_belongs_to_project(run.run_id, tasks)]
        metric_keys = sorted(
            {
                metric_key
                for run in runs
                for metric_key in self._flatten_numeric_metrics(run.metrics).keys()
            }
        )
        branches = []
        for run in runs:
            metrics = self._flatten_numeric_metrics(run.metrics)
            primary_metric, primary_value = self._primary_metric(metrics)
            source_task_id = self._task_id_for_run(run.run_id, tasks)
            branch_name = run.experiment_branch or self._task_branch_name(source_task_id, tasks)
            branches.append(
                BranchRunSummary(
                    run_id=run.run_id,
                    status=run.status,
                    branch_name=branch_name,
                    primary_metric=primary_metric,
                    primary_value=primary_value,
                    metrics=metrics,
                    source_task_id=source_task_id,
                )
            )
        branches.sort(
            key=lambda item: (
                item.branch_name or "~",
                item.primary_value is None,
                -(item.primary_value or 0.0),
                item.run_id,
            )
        )
        return BranchComparison(
            project_id=project_id,
            metric_keys=tuple(metric_keys),
            branches=tuple(branches),
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

    def latest_project_strategy(self, project_id: str):
        project = self.project_service.get_project(project_id)
        if project is None:
            raise KeyError(f"Project not found: {project_id}")
        return self.strategy_service.latest_project_strategy(
            project_id=project_id,
            tasks=self.task_service.list_tasks(),
        )

    def task_retrieval_evidence(self, task_id: str):
        task = self.task_service.get_task(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        return tuple(task.latest_retrieval_evidence)

    def search_project_memory(self, project_id: str, query: str, *, limit: int = 12):
        project = self.project_service.get_project(project_id)
        if project is None:
            raise KeyError(f"Project not found: {project_id}")
        return tuple(
            self.memory_registry_service.search(project_id=project_id, query=query, limit=limit)
            if query.strip()
            else self.memory_registry_service.list_records(project_id=project_id)[:limit]
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
    def _run_belongs_to_project(run_id: str, tasks) -> bool:
        return any(run_id == f"run-{task.task_id}" or run_id == task.task_id for task in tasks)

    @staticmethod
    def _task_id_for_run(run_id: str, tasks) -> str | None:
        for task in tasks:
            if run_id == f"run-{task.task_id}" or run_id == task.task_id:
                return task.task_id
        return None

    @staticmethod
    def _task_branch_name(task_id: str | None, tasks) -> str | None:
        if task_id is None:
            return None
        task = next((item for item in tasks if item.task_id == task_id), None)
        if task is None:
            return None
        branch_name = str(task.input_payload.get("branch_name", "")).strip()
        if branch_name:
            return branch_name
        if task.fanout_group:
            return task.fanout_group
        return task.parent_task_id

    @classmethod
    def _flatten_numeric_metrics(
        cls,
        payload: dict[str, object] | None,
        *,
        prefix: str = "",
    ) -> dict[str, float]:
        if not isinstance(payload, dict):
            return {}
        flattened: dict[str, float] = {}
        for key, value in payload.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                flattened.update(cls._flatten_numeric_metrics(value, prefix=name))
                continue
            if isinstance(value, bool):
                continue
            if isinstance(value, (int, float)):
                flattened[name] = float(value)
        return flattened

    @staticmethod
    def _primary_metric(metrics: dict[str, float]) -> tuple[str | None, float | None]:
        priority = ("accuracy", "acc", "f1", "auc", "bleu", "rouge", "loss")
        for key in priority:
            for metric_name, metric_value in metrics.items():
                if key in metric_name.lower():
                    return metric_name, metric_value
        if not metrics:
            return None, None
        first_key = sorted(metrics)[0]
        return first_key, metrics[first_key]

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
        if completed_kinds.intersection({"style_pass", "polish_draft", "archive_research", "archive_run"}):
            return (
                "archive_research",
                "The core loop is populated. Archive lessons and provenance before starting the next cycle.",
                "archive_entry",
                None,
            )
        if not completed_kinds.intersection(
            {"analyze_run", "branch_review", "review_build", "audit_run", "verify_evidence", "verify_results"}
        ):
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
