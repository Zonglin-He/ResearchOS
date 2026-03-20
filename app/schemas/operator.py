from __future__ import annotations

from dataclasses import dataclass, field

from app.core.paths import StorageBoundary
from app.routing.models import ProviderHealthSnapshot, ResolvedDispatch


@dataclass(frozen=True)
class ProjectDashboard:
    project_id: str
    project_name: str
    project_status: str
    total_tasks: int
    queued_tasks: int
    running_tasks: int
    waiting_approval_tasks: int
    succeeded_tasks: int
    failed_tasks: int
    cancelled_tasks: int
    artifact_count: int
    paper_card_count: int
    gap_map_count: int
    run_count: int
    latest_task_ids: tuple[str, ...] = ()
    topic_freeze_present: bool = False
    spec_freeze_present: bool = False
    results_freeze_present: bool = False
    recommended_next_task_kind: str | None = None
    recommendation_reason: str = ""
    expected_artifact: str = ""
    likely_next_task_kind: str | None = None
    storage_boundary: StorageBoundary | None = None


@dataclass(frozen=True)
class RoutingInspection:
    scope: str
    subject_id: str | None
    resolved_dispatch: ResolvedDispatch
    provider_health: tuple[ProviderHealthSnapshot, ...] = ()
    storage_boundary: StorageBoundary | None = None


@dataclass(frozen=True)
class ArtifactInspection:
    artifact_id: str
    run_id: str
    kind: str
    path: str
    exists_on_disk: bool
    verification_count: int
    audit_entry_count: int
    annotation_count: int
    evidence_refs: tuple[str, ...] = ()
    claim_supports: tuple[str, ...] = ()
    related_freeze_ids: tuple[str, ...] = ()
    metadata: dict[str, object] = field(default_factory=dict)
    resolved_path: str = ""
    workspace_relative_path: str | None = None
