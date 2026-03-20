from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from app.schemas.approval import Approval
from app.schemas.experiment import (
    ExperimentBudget,
    ExperimentDecision,
    ExperimentDecisionKind,
    ExperimentProposal,
    ExperimentProposalStatus,
    ExperimentResultSummary,
)
from app.schemas.run_manifest import RunManifest
from app.services.approval_service import ApprovalService
from app.services.experiment_registry import ExperimentRegistry
from app.services.freeze_service import FreezeService
from app.services.run_service import RunService
from app.services.task_service import TaskService


@dataclass
class ExperimentExecutionRecord:
    proposal: ExperimentProposal
    run_manifest: RunManifest


class ExperimentManager:
    def __init__(
        self,
        *,
        registry: ExperimentRegistry,
        task_service: TaskService,
        run_service: RunService,
        freeze_service: FreezeService,
        approval_service: ApprovalService,
    ) -> None:
        self.registry = registry
        self.task_service = task_service
        self.run_service = run_service
        self.freeze_service = freeze_service
        self.approval_service = approval_service

    def enqueue_proposal(
        self,
        *,
        task_id: str,
        proposal: ExperimentProposal,
        budget: ExperimentBudget,
    ) -> ExperimentProposal:
        self.registry.save_budget(budget)
        proposal.requires_approval = proposal.estimated_cost > budget.require_approval_above
        proposal.status = ExperimentProposalStatus.QUEUED
        self.registry.save_proposal(proposal)
        self.task_service.attach_experiment_proposal(task_id, proposal.proposal_id)
        return proposal

    def list_queue(self, spec_id: str | None = None) -> list[ExperimentProposal]:
        proposals = self.registry.list_proposals()
        queued = [proposal for proposal in proposals if proposal.status == ExperimentProposalStatus.QUEUED]
        if spec_id is not None:
            queued = [proposal for proposal in queued if proposal.spec_id == spec_id]
        return queued

    def authorize_execution(self, proposal_id: str) -> ExperimentDecision | None:
        proposal = self._require_proposal(proposal_id)
        budget = self._require_budget(proposal.spec_id)
        spec_freeze = self.freeze_service.load_spec_freeze()
        if spec_freeze is None or spec_freeze.spec_id != proposal.spec_id or spec_freeze.status != "approved":
            return self._record_blocking_decision(
                proposal,
                decision=ExperimentDecisionKind.BLOCK,
                reason="Spec freeze must exist and be approved before execution.",
            )

        if budget.attempts_used >= budget.max_attempts:
            return self._record_blocking_decision(
                proposal,
                decision=ExperimentDecisionKind.STOP,
                reason=f"Max attempts reached ({budget.max_attempts}).",
            )

        if budget.total_cost_spent >= budget.max_total_cost:
            return self._record_blocking_decision(
                proposal,
                decision=ExperimentDecisionKind.STOP,
                reason=f"Budget cap reached ({budget.max_total_cost}).",
            )

        if proposal.requires_approval and not self._has_approved_execution(proposal.proposal_id):
            self._ensure_pending_approval(proposal)
            return self._record_blocking_decision(
                proposal,
                decision=ExperimentDecisionKind.REQUIRES_APPROVAL,
                reason="Estimated cost exceeds approval threshold.",
                approval_required=True,
            )

        proposal.status = ExperimentProposalStatus.READY
        self.registry.save_proposal(proposal)
        return None

    def record_execution(
        self,
        *,
        proposal_id: str,
        run_manifest: RunManifest,
    ) -> ExperimentExecutionRecord:
        proposal = self._require_proposal(proposal_id)
        proposal.status = ExperimentProposalStatus.EXECUTED
        self.registry.save_proposal(proposal)
        run_manifest.experiment_proposal_id = proposal.proposal_id
        run_manifest.experiment_branch = proposal.branch_name or None
        self.run_service.update_run(run_manifest)
        return ExperimentExecutionRecord(proposal=proposal, run_manifest=run_manifest)

    def evaluate_result(
        self,
        *,
        proposal_id: str,
        result_summary: ExperimentResultSummary,
    ) -> ExperimentDecision:
        proposal = self._require_proposal(proposal_id)
        budget = self._require_budget(proposal.spec_id)
        self.registry.append_result(result_summary)

        budget.attempts_used += 1
        budget.total_cost_spent += result_summary.cost_spent
        self.registry.save_budget(budget)

        improvement = round(result_summary.primary_value - result_summary.baseline_value, 6)
        within_budget = budget.total_cost_spent <= budget.max_total_cost

        if not result_summary.improved and budget.stop_on_no_improvement:
            decision = ExperimentDecision(
                decision_id=f"{proposal_id}:decision:{budget.attempts_used}",
                proposal_id=proposal_id,
                run_id=result_summary.run_id,
                decision=ExperimentDecisionKind.DISCARD,
                reason="No improvement over baseline; deterministic stop-on-no-improvement triggered.",
                improvement=improvement,
                within_budget=within_budget,
                branch_action="rollback_to_base",
            )
        elif not within_budget:
            decision = ExperimentDecision(
                decision_id=f"{proposal_id}:decision:{budget.attempts_used}",
                proposal_id=proposal_id,
                run_id=result_summary.run_id,
                decision=ExperimentDecisionKind.DISCARD,
                reason="Run exceeded the configured experiment budget.",
                improvement=improvement,
                within_budget=False,
                branch_action="rollback_to_base",
            )
        else:
            decision = ExperimentDecision(
                decision_id=f"{proposal_id}:decision:{budget.attempts_used}",
                proposal_id=proposal_id,
                run_id=result_summary.run_id,
                decision=ExperimentDecisionKind.KEEP,
                reason="Run improved over baseline within budget.",
                improvement=improvement,
                within_budget=True,
                branch_action="keep_branch",
            )

        proposal.status = ExperimentProposalStatus.DECIDED
        self.registry.save_proposal(proposal)
        self.registry.append_decision(decision)
        run_manifest = self.run_service.get_run(result_summary.run_id)
        if run_manifest is not None:
            run_manifest.status = "completed"
            run_manifest.metrics[result_summary.primary_metric] = result_summary.primary_value
            run_manifest.metrics["baseline"] = result_summary.baseline_value
            run_manifest.metrics["improvement"] = improvement
            self.run_service.update_run(run_manifest)
        return decision

    def _has_approved_execution(self, proposal_id: str) -> bool:
        approvals = self.approval_service.list_approvals()
        return any(
            approval.target_type == "experiment_proposal"
            and approval.target_id == proposal_id
            and approval.decision == "approved"
            for approval in approvals
        )

    def _ensure_pending_approval(self, proposal: ExperimentProposal) -> None:
        existing = [
            approval
            for approval in self.approval_service.list_approvals()
            if approval.target_type == "experiment_proposal" and approval.target_id == proposal.proposal_id
        ]
        if existing:
            return
        task = self.task_service.get_task(proposal.task_id)
        approval = Approval(
            approval_id=f"approval:{proposal.proposal_id}",
            project_id=task.project_id if task is not None else "",
            target_type="experiment_proposal",
            target_id=proposal.proposal_id,
            approved_by="system",
            decision="pending",
            comment="Approval required before expensive experiment execution.",
        )
        self.approval_service.record_approval(approval)

    def _record_blocking_decision(
        self,
        proposal: ExperimentProposal,
        *,
        decision: ExperimentDecisionKind,
        reason: str,
        approval_required: bool = False,
    ) -> ExperimentDecision:
        proposal.status = ExperimentProposalStatus.BLOCKED
        self.registry.save_proposal(proposal)
        record = ExperimentDecision(
            decision_id=f"{proposal.proposal_id}:{decision.value}",
            proposal_id=proposal.proposal_id,
            decision=decision,
            reason=reason,
            approval_required=approval_required,
            within_budget=True,
            branch_action="hold",
        )
        self.registry.append_decision(record)
        return record

    def _require_proposal(self, proposal_id: str) -> ExperimentProposal:
        proposal = self.registry.get_proposal(proposal_id)
        if proposal is None:
            raise KeyError(f"Experiment proposal not found: {proposal_id}")
        return proposal

    def _require_budget(self, spec_id: str) -> ExperimentBudget:
        budget = self.registry.get_budget(spec_id)
        if budget is None:
            raise KeyError(f"Experiment budget not found for spec: {spec_id}")
        return budget
