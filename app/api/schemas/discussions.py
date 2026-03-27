from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DiscussionEntityRefModel(BaseModel):
    entity_type: str
    entity_id: str
    label: str = ""


class DiscussionCoverageCheckRead(BaseModel):
    ref: str
    ref_type: str
    status: str
    note: str = ""
    linked_entity_id: str | None = None


class DiscussionCoverageRead(BaseModel):
    checks: list[DiscussionCoverageCheckRead] = Field(default_factory=list)
    summary: str = ""


class DiscussionDistillationRead(BaseModel):
    summary: str = ""
    findings: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    literature_notes: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    counterarguments: list[str] = Field(default_factory=list)
    suggested_next_actions: list[str] = Field(default_factory=list)
    cited_dois: list[str] = Field(default_factory=list)
    referenced_claim_ids: list[str] = Field(default_factory=list)


class DiscussionImportRead(BaseModel):
    source_mode: str
    provider_label: str
    verbatim_text: str
    transcript_title: str = ""
    cited_dois: list[str] = Field(default_factory=list)
    referenced_claim_ids: list[str] = Field(default_factory=list)
    imported_at: datetime


class DiscussionContextBundleRead(BaseModel):
    bundle_id: str
    project_id: str
    stage: str
    branch_kind: str
    target_kind: str
    target_id: str
    target_label: str
    research_goal: str
    focus_question: str
    operator_prompt: str
    current_state: dict[str, Any] = Field(default_factory=dict)
    controversies: list[str] = Field(default_factory=list)
    questions_to_answer: list[str] = Field(default_factory=list)
    attached_entities: list[DiscussionEntityRefModel] = Field(default_factory=list)
    handoff_packet: str = ""
    created_at: datetime


class DiscussionSessionCreate(BaseModel):
    session_id: str
    project_id: str
    title: str
    source_type: str = "web_handoff"
    source_label: str = ""
    branch_kind: str = "idea-branch"
    target_kind: str
    target_id: str
    target_label: str = ""
    focus_question: str = ""
    operator_prompt: str = ""
    questions_to_answer: list[str] = Field(default_factory=list)
    attached_entities: list[DiscussionEntityRefModel] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DiscussionImportCreate(BaseModel):
    source_mode: str = "web"
    provider_label: str = ""
    verbatim_text: str
    transcript_title: str = ""
    cited_dois: list[str] = Field(default_factory=list)
    referenced_claim_ids: list[str] = Field(default_factory=list)
    findings: list[str] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    literature_notes: list[str] = Field(default_factory=list)
    open_questions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    counterarguments: list[str] = Field(default_factory=list)
    suggested_next_actions: list[str] = Field(default_factory=list)
    summary: str = ""


class DiscussionAdoptCreate(BaseModel):
    approved_by: str = "operator"
    adopted_summary: str = ""
    route_to_kb: bool = True


class DiscussionPromoteApprovalCreate(BaseModel):
    approved_by: str = "operator"


class DiscussionPromoteTaskCreate(BaseModel):
    owner: str = "operator"
    task_kind: str = ""
    task_goal: str = ""


class DiscussionPromotionRead(BaseModel):
    promotion_type: str
    record_ids: list[str] = Field(default_factory=list)


class DiscussionSessionRead(BaseModel):
    session_id: str
    project_id: str
    title: str
    source_type: str
    source_label: str = ""
    status: str
    stage: str
    branch_kind: str
    target_kind: str
    target_id: str
    target_label: str
    focus_question: str = ""
    operator_prompt: str = ""
    attached_entities: list[DiscussionEntityRefModel] = Field(default_factory=list)
    context_bundle: DiscussionContextBundleRead | None = None
    latest_import: DiscussionImportRead | None = None
    machine_distilled: DiscussionDistillationRead | None = None
    adopted_decision: DiscussionDistillationRead | None = None
    coverage_report: DiscussionCoverageRead | None = None
    promoted_record_ids: dict[str, list[str]] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime
