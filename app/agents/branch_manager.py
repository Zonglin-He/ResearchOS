from __future__ import annotations

from typing import Any

from app.agents.llm_agent import PromptDrivenAgent
from app.agents.response_schemas import BRANCH_PLAN_RESPONSE_SCHEMA, BRANCH_REVIEW_RESPONSE_SCHEMA
from app.core.enums import Stage
from app.roles import analyst_role_binding
from app.schemas.context import RunContext
from app.schemas.freeze import ResultsFreeze
from app.schemas.result import AgentResult
from app.schemas.task import Task
from app.services.checkpoint_service import CheckpointService
from app.services.freeze_service import FreezeService
from app.services.task_service import TaskService
from app.schemas.task import TaskStatus


class BranchManagerAgent(PromptDrivenAgent):
    name = "branch_manager_agent"
    description = "Plans experiment branches and selects the winning branch after fanout runs complete."
    prompt_path = "prompts/branch_manager.md"
    enable_reflection = True
    role_binding = analyst_role_binding()

    def __init__(
        self,
        provider,
        *,
        task_service: TaskService,
        checkpoint_service: CheckpointService | None = None,
        freeze_service: FreezeService | None = None,
        model: str | None = None,
        tool_registry=None,
        provider_registry=None,
        routing_policy=None,
        provider_invocation_service=None,
        role_prompt_registry=None,
        role_skill_registry=None,
    ) -> None:
        super().__init__(
            provider,
            model=model,
            response_schema=BRANCH_PLAN_RESPONSE_SCHEMA,
            tool_registry=tool_registry,
            provider_registry=provider_registry,
            routing_policy=routing_policy,
            provider_invocation_service=provider_invocation_service,
            role_binding=self.role_binding,
            role_prompt_registry=role_prompt_registry,
            role_skill_registry=role_skill_registry,
        )
        self.task_service = task_service
        self.checkpoint_service = checkpoint_service
        self.freeze_service = freeze_service

    def get_response_schema(self, task: Task, ctx: RunContext) -> dict[str, Any] | None:
        if task.kind == "branch_review":
            return BRANCH_REVIEW_RESPONSE_SCHEMA
        return BRANCH_PLAN_RESPONSE_SCHEMA

    def build_user_payload(self, task: Task, ctx: RunContext) -> dict[str, Any]:
        payload = super().build_user_payload(task, ctx)
        if task.kind == "branch_review":
            payload["branch_reports"] = self._branch_reports(task)
            payload["branch_manager_focus"] = {
                "mode": "review",
                "goal": "Choose the strongest surviving branch and justify why the others should be pruned.",
            }
        else:
            payload["branch_manager_focus"] = {
                "mode": "plan",
                "goal": "Turn one selected idea into 2-3 concrete, parallelizable experiment branches.",
            }
        return payload

    def build_result(self, task: Task, ctx: RunContext, output: dict[str, Any]) -> AgentResult:
        if task.kind == "branch_review":
            return self._build_review_result(task, output)
        return self._build_plan_result(task, output)

    def _build_plan_result(self, task: Task, output: dict[str, Any]) -> AgentResult:
        branches = output.get("branches", [])
        if not isinstance(branches, list) or not branches:
            branches = self._fallback_branches(task)
            output.setdefault("audit_notes", []).append("branch manager fallback synthesized branch plans")

        fanout_group = task.fanout_group or f"{task.task_id}:branch-fanout"
        next_tasks: list[Task] = []
        review_dependencies: list[str] = []
        for index, branch in enumerate(branches[:3], start=1):
            branch_task_id = f"{task.task_id}:branch-{index:02d}"
            review_dependencies.append(f"{branch_task_id}:analyze_run")
            next_tasks.append(
                Task(
                    task_id=branch_task_id,
                    project_id=task.project_id,
                    kind="implement_experiment",
                    goal=f"Run branch {branch.get('title', branch.get('branch_id', index))}",
                    input_payload={
                        **task.input_payload,
                        "branch_id": branch.get("branch_id", f"branch-{index}"),
                        "branch_title": branch.get("title", f"Branch {index}"),
                        "branch_hypothesis": branch.get("hypothesis", ""),
                        "branch_plan": branch,
                        "branch_constraints": branch.get("constraints", []),
                        "datasets": branch.get("datasets", []),
                        "metrics": branch.get("metrics", []),
                        "expected_gain": branch.get("expected_gain", ""),
                        "project_stage": Stage.RUN_EXPERIMENTS.value,
                    },
                    owner=task.owner,
                    assigned_agent="builder_agent",
                    parent_task_id=task.task_id,
                    fanout_group=fanout_group,
                    join_key="branch_exploration",
                )
            )

        next_tasks.append(
            Task(
                task_id=f"{task.task_id}:branch_review",
                project_id=task.project_id,
                kind="branch_review",
                goal="Compare experiment branches and choose the branch to keep.",
                input_payload={
                    **task.input_payload,
                    "branches": branches,
                    "fanout_group": fanout_group,
                    "target_venue": task.input_payload.get("target_venue", ""),
                },
                owner=task.owner,
                assigned_agent="branch_manager_agent",
                parent_task_id=task.task_id,
                depends_on=review_dependencies,
                fanout_group=fanout_group,
                join_key="branch_review",
            )
        )

        return AgentResult(
            status="success",
            output={"summary": output.get("summary", ""), "branches": branches},
            next_tasks=next_tasks,
            audit_notes=output.get("audit_notes", []),
        )

    def _build_review_result(self, task: Task, output: dict[str, Any]) -> AgentResult:
        branch_reports = self._branch_reports(task)
        selected_branch_id = str(output.get("selected_branch_id", "")).strip() or self._fallback_selected_branch(branch_reports)
        selected_report = next((report for report in branch_reports if report.get("branch_id") == selected_branch_id), None)
        if selected_report is None and branch_reports:
            selected_report = branch_reports[0]
            selected_branch_id = str(selected_report.get("branch_id", "")).strip()

        winning_rationale = str(output.get("winning_rationale", "")).strip() or "Selected the branch with the strongest observed metrics."
        recommended_next_step = str(output.get("recommended_next_step", "")).strip() or "write_draft"
        discarded = output.get("discarded_branches", [])
        next_tasks: list[Task] = []

        if selected_report is not None:
            run_id = selected_report.get("run_id", "")
            artifact_ids = selected_report.get("artifact_ids", [])
            metrics = selected_report.get("metrics", {})
            claim_ids = selected_report.get("claim_ids", [])
            next_tasks.append(
                Task(
                    task_id=f"{task.task_id}:write_draft",
                    project_id=task.project_id,
                    kind="write_draft",
                    goal=f"Write the draft from winning branch {selected_branch_id}",
                    input_payload={
                        "run_id": run_id,
                        "artifact_ids": artifact_ids,
                        "claim_ids": claim_ids,
                        "metrics": metrics,
                        "target_venue": task.input_payload.get("target_venue", ""),
                        "branch_id": selected_branch_id,
                        "winning_rationale": winning_rationale,
                        "discarded_branches": discarded,
                    },
                    owner=task.owner,
                    assigned_agent="writer_agent",
                    parent_task_id=task.task_id,
                )
            )
            if self.freeze_service is not None:
                self.freeze_service.save_results_freeze(
                    ResultsFreeze(
                        results_id=f"{task.project_id}-branch-results",
                        spec_id=str(task.input_payload.get("spec_id", task.task_id)),
                        main_claims=[winning_rationale],
                        tables=[selected_branch_id],
                        figures=[],
                        approved_by="system",
                        status="approved",
                    )
                )

        return AgentResult(
            status="success",
            output={
                "summary": output.get("summary", ""),
                "selected_branch_id": selected_branch_id,
                "winning_rationale": winning_rationale,
                "discarded_branches": discarded,
                "recommended_next_step": recommended_next_step,
            },
            next_tasks=next_tasks,
            audit_notes=output.get("audit_notes", []),
        )

    def _branch_reports(self, task: Task) -> list[dict[str, Any]]:
        reports: list[dict[str, Any]] = []
        for dependency_id in task.depends_on:
            dependency = self.task_service.get_task(dependency_id)
            if dependency is None or dependency.status != TaskStatus.SUCCEEDED:
                continue
            checkpoint = None if self.checkpoint_service is None else self.checkpoint_service.load(dependency.task_id)
            payload = checkpoint.get("payload", {}) if isinstance(checkpoint, dict) else {}
            result_output = payload.get("output", {}) if isinstance(payload, dict) else {}
            reports.append(
                {
                    "task_id": dependency.task_id,
                    "branch_id": dependency.input_payload.get("branch_id") or dependency.input_payload.get("run_id", dependency.task_id),
                    "run_id": dependency.input_payload.get("run_id", ""),
                    "artifact_ids": dependency.input_payload.get("artifact_ids", []),
                    "claim_ids": dependency.input_payload.get("claim_ids", []),
                    "metrics": result_output.get("metrics", dependency.input_payload.get("metrics", {})),
                    "summary": result_output.get("summary", ""),
                    "decision": result_output.get("decision", ""),
                    "execution_success": result_output.get("execution_success", True),
                    "anomalies": result_output.get("anomalies", []),
                }
            )
        return reports

    @staticmethod
    def _fallback_selected_branch(branch_reports: list[dict[str, Any]]) -> str:
        if not branch_reports:
            return ""
        scored = sorted(
            branch_reports,
            key=lambda item: BranchManagerAgent._score_metrics(item.get("metrics", {})),
            reverse=True,
        )
        return str(scored[0].get("branch_id", ""))

    @staticmethod
    def _score_metrics(metrics: Any) -> float:
        if not isinstance(metrics, dict):
            return 0.0
        numeric = [float(value) for value in metrics.values() if isinstance(value, (int, float))]
        return max(numeric) if numeric else 0.0

    @staticmethod
    def _fallback_branches(task: Task) -> list[dict[str, Any]]:
        datasets = task.input_payload.get("datasets", []) or ["default-dataset"]
        metrics = task.input_payload.get("metrics", []) or ["accuracy"]
        selected_gap = str(task.input_payload.get("selected_gap_id", "selected-gap"))
        return [
            {
                "branch_id": "branch-baseline",
                "title": "Baseline reproduction",
                "hypothesis": f"Reproduce a strong baseline for {selected_gap} before extending it.",
                "datasets": datasets[:1],
                "metrics": metrics[:1],
                "feasibility": "high",
                "expected_gain": "Establish a trustworthy comparison anchor.",
                "constraints": ["keep compute low", "match published baseline budget"],
            },
            {
                "branch_id": "branch-extension",
                "title": "Main method extension",
                "hypothesis": f"Test the core extension proposed by {selected_gap}.",
                "datasets": datasets[:1],
                "metrics": metrics[:1],
                "feasibility": "medium",
                "expected_gain": "Primary novelty branch.",
                "constraints": ["single change over baseline", "preserve fairness controls"],
            },
            {
                "branch_id": "branch-lowcost",
                "title": "Low-cost ablation",
                "hypothesis": f"Probe whether {selected_gap} still holds under a cheaper setup.",
                "datasets": datasets[:1],
                "metrics": metrics[:1],
                "feasibility": "high",
                "expected_gain": "Validate robustness under limited compute.",
                "constraints": ["reduced training budget", "report trade-offs explicitly"],
            },
        ]
