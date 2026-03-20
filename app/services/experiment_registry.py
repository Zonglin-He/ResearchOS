from __future__ import annotations

from pathlib import Path

from app.schemas.experiment import (
    ExperimentBudget,
    ExperimentDecision,
    ExperimentDecisionKind,
    ExperimentProposal,
    ExperimentProposalStatus,
    ExperimentResultSummary,
)
from app.services.registry_store import append_jsonl, read_jsonl, to_record, upsert_jsonl


class ExperimentRegistry:
    def __init__(self, base_dir: str | Path = "registry/experiments") -> None:
        self.base_dir = Path(base_dir)
        self.proposals_path = self.base_dir / "proposals.jsonl"
        self.budgets_path = self.base_dir / "budgets.jsonl"
        self.results_path = self.base_dir / "results.jsonl"
        self.decisions_path = self.base_dir / "decisions.jsonl"

    def save_budget(self, budget: ExperimentBudget) -> ExperimentBudget:
        upsert_jsonl(self.budgets_path, "spec_id", to_record(budget))
        return budget

    def get_budget(self, spec_id: str) -> ExperimentBudget | None:
        for row in read_jsonl(self.budgets_path):
            if row.get("spec_id") == spec_id:
                return ExperimentBudget(**row)
        return None

    def save_proposal(self, proposal: ExperimentProposal) -> ExperimentProposal:
        upsert_jsonl(self.proposals_path, "proposal_id", to_record(proposal))
        return proposal

    def get_proposal(self, proposal_id: str) -> ExperimentProposal | None:
        for row in read_jsonl(self.proposals_path):
            if row.get("proposal_id") == proposal_id:
                row["status"] = ExperimentProposalStatus(row["status"])
                return ExperimentProposal(**row)
        return None

    def list_proposals(self) -> list[ExperimentProposal]:
        proposals: list[ExperimentProposal] = []
        for row in read_jsonl(self.proposals_path):
            row["status"] = ExperimentProposalStatus(row["status"])
            proposals.append(ExperimentProposal(**row))
        return proposals

    def append_result(self, summary: ExperimentResultSummary) -> ExperimentResultSummary:
        append_jsonl(self.results_path, to_record(summary))
        return summary

    def list_results(self, proposal_id: str | None = None) -> list[ExperimentResultSummary]:
        results: list[ExperimentResultSummary] = []
        for row in read_jsonl(self.results_path):
            if proposal_id is not None and row.get("proposal_id") != proposal_id:
                continue
            results.append(ExperimentResultSummary(**row))
        return results

    def append_decision(self, decision: ExperimentDecision) -> ExperimentDecision:
        append_jsonl(self.decisions_path, to_record(decision))
        return decision

    def list_decisions(self, proposal_id: str | None = None) -> list[ExperimentDecision]:
        decisions: list[ExperimentDecision] = []
        for row in read_jsonl(self.decisions_path):
            if proposal_id is not None and row.get("proposal_id") != proposal_id:
                continue
            row["decision"] = ExperimentDecisionKind(row["decision"])
            decisions.append(ExperimentDecision(**row))
        return decisions
