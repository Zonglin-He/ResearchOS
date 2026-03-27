from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass
class DiscussionEntityRef:
    entity_type: str
    entity_id: str
    label: str = ""


@dataclass
class DiscussionCoverageCheck:
    ref: str
    ref_type: str
    status: str
    note: str = ""
    linked_entity_id: str | None = None


@dataclass
class DiscussionCoverageReport:
    checks: list[DiscussionCoverageCheck] = field(default_factory=list)
    summary: str = ""


@dataclass
class DiscussionDistillation:
    summary: str = ""
    findings: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    literature_notes: list[str] = field(default_factory=list)
    open_questions: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    counterarguments: list[str] = field(default_factory=list)
    suggested_next_actions: list[str] = field(default_factory=list)
    cited_dois: list[str] = field(default_factory=list)
    referenced_claim_ids: list[str] = field(default_factory=list)


@dataclass
class DiscussionImportRecord:
    source_mode: str
    provider_label: str
    verbatim_text: str
    transcript_title: str = ""
    cited_dois: list[str] = field(default_factory=list)
    referenced_claim_ids: list[str] = field(default_factory=list)
    imported_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DiscussionContextBundle:
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
    current_state: dict[str, Any] = field(default_factory=dict)
    controversies: list[str] = field(default_factory=list)
    questions_to_answer: list[str] = field(default_factory=list)
    attached_entities: list[DiscussionEntityRef] = field(default_factory=list)
    handoff_packet: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DiscussionSession:
    session_id: str
    project_id: str
    title: str
    source_type: str
    source_label: str = ""
    status: str = "draft"
    stage: str = ""
    branch_kind: str = "idea-branch"
    target_kind: str = "project"
    target_id: str = ""
    target_label: str = ""
    focus_question: str = ""
    operator_prompt: str = ""
    attached_entities: list[DiscussionEntityRef] = field(default_factory=list)
    context_bundle: DiscussionContextBundle | None = None
    latest_import: DiscussionImportRecord | None = None
    machine_distilled: DiscussionDistillation | None = None
    adopted_decision: DiscussionDistillation | None = None
    coverage_report: DiscussionCoverageReport | None = None
    promoted_record_ids: dict[str, list[str]] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
