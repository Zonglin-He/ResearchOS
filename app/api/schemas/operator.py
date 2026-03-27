from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field

from app.api.schemas.routing import ProviderHealthSnapshotModel, ResolvedDispatchModel


class StorageBoundaryRead(BaseModel):
    database_backend: str
    database_location: str
    registry_dir: str
    artifacts_dir: str
    freezes_dir: str
    state_dir: str


class ProjectDashboardRead(BaseModel):
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
    latest_task_ids: list[str] = Field(default_factory=list)
    topic_freeze_present: bool
    spec_freeze_present: bool
    results_freeze_present: bool
    recommended_next_task_kind: str | None = None
    recommendation_reason: str = ""
    expected_artifact: str = ""
    likely_next_task_kind: str | None = None
    flow_snapshot: dict[str, object] = Field(default_factory=dict)
    available_flow_actions: list[str] = Field(default_factory=list)
    storage_boundary: StorageBoundaryRead | None = None


class RoutingInspectionRead(BaseModel):
    scope: str
    subject_id: str | None = None
    resolved_dispatch: ResolvedDispatchModel
    provider_health: list[ProviderHealthSnapshotModel] = Field(default_factory=list)
    storage_boundary: StorageBoundaryRead | None = None


class ArtifactInspectionRead(BaseModel):
    artifact_id: str
    run_id: str
    kind: str
    path: str
    exists_on_disk: bool
    verification_count: int
    audit_entry_count: int
    annotation_count: int
    evidence_refs: list[str] = Field(default_factory=list)
    claim_supports: list[str] = Field(default_factory=list)
    related_freeze_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, object] = Field(default_factory=dict)
    resolved_path: str
    workspace_relative_path: str | None = None


class BranchRunSummaryRead(BaseModel):
    run_id: str
    status: str
    branch_name: str | None = None
    primary_metric: str | None = None
    primary_value: float | None = None
    metrics: dict[str, float] = Field(default_factory=dict)
    source_task_id: str | None = None


class BranchComparisonRead(BaseModel):
    project_id: str
    metric_keys: list[str] = Field(default_factory=list)
    branches: list[BranchRunSummaryRead] = Field(default_factory=list)


class FlowActionRequest(BaseModel):
    stage: str | None = None
    task_id: str | None = None
    note: str = ""


class FlowSnapshotRead(BaseModel):
    stage: str
    status: str
    decision: str
    checkpoint_required: bool
    active_task_id: str | None = None
    rollback_stage: str | None = None
    note: str = ""
    updated_at: datetime
    available_actions: list[str] = Field(default_factory=list)
    history: list[dict[str, object]] = Field(default_factory=list)
