from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum


class ExperimentProposalStatus(str, Enum):
    QUEUED = "queued"
    READY = "ready"
    BLOCKED = "blocked"
    EXECUTED = "executed"
    DECIDED = "decided"


class ExperimentDecisionKind(str, Enum):
    KEEP = "keep"
    DISCARD = "discard"
    REQUIRES_APPROVAL = "requires_approval"
    BLOCK = "block"
    STOP = "stop"


@dataclass
class ExperimentBudget:
    spec_id: str
    max_attempts: int = 3
    max_total_cost: float = 100.0
    attempts_used: int = 0
    total_cost_spent: float = 0.0
    stop_on_no_improvement: bool = True
    require_approval_above: float = 50.0


@dataclass
class ExperimentProposal:
    proposal_id: str
    task_id: str
    spec_id: str
    title: str
    hypothesis: str
    proposed_by: str
    execution_command: str
    objective_metric: str
    estimated_cost: float = 0.0
    branch_name: str = ""
    base_commit: str = ""
    parent_run_id: str | None = None
    requires_approval: bool = False
    status: ExperimentProposalStatus = ExperimentProposalStatus.QUEUED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ExperimentResultSummary:
    proposal_id: str
    run_id: str
    primary_metric: str
    primary_value: float
    baseline_value: float
    cost_spent: float
    improved: bool
    notes: list[str] = field(default_factory=list)
    artifacts: list[str] = field(default_factory=list)
    evaluated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ExperimentDecision:
    decision_id: str
    proposal_id: str
    decision: ExperimentDecisionKind
    reason: str
    run_id: str | None = None
    improvement: float | None = None
    within_budget: bool = True
    approval_required: bool = False
    branch_action: str = "hold"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
