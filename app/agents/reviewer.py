from __future__ import annotations

from typing import Any

from app.agents.llm_agent import PromptDrivenAgent
from app.agents.response_schemas import REVIEWER_RESPONSE_SCHEMA
from app.agents.utils import build_child_task
from app.roles import reviewer_role_binding
from app.schemas.result import AgentResult
from app.schemas.task import Task
from app.services.kb_service import KnowledgeBaseService, KnowledgeRecord


class ReviewerAgent(PromptDrivenAgent):
    name = "reviewer_agent"
    description = "Reviews code, experiments, and claims for validity."
    prompt_path = "prompts/reviewer.md"
    role_binding = reviewer_role_binding()

    def __init__(
        self,
        provider,
        *,
        kb_service: KnowledgeBaseService | None = None,
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
            response_schema=REVIEWER_RESPONSE_SCHEMA,
            tool_registry=tool_registry,
            provider_registry=provider_registry,
            routing_policy=routing_policy,
            provider_invocation_service=provider_invocation_service,
            role_binding=self.role_binding,
            role_prompt_registry=role_prompt_registry,
            role_skill_registry=role_skill_registry,
        )
        self.kb_service = kb_service

    def build_user_payload(self, task, ctx) -> dict[str, Any]:
        payload = super().build_user_payload(task, ctx)
        if task.kind == "gap_debate":
            payload["reviewer_focus"] = {
                "mode": "challenger",
                "required_outputs": [
                    "decision",
                    "summary",
                    "debate_weaknesses",
                    "recommended_constraints",
                    "audit_notes",
                ],
                "review_axes": [
                    "novelty weakness",
                    "feasibility risk",
                    "missing baseline",
                    "unclear evidence chain",
                    "overclaim risk",
                ],
            }
        else:
            payload["reviewer_focus"] = {
                "required_outputs": [
                    "decision",
                    "summary",
                    "blocking_issues",
                    "audit_notes",
                    "claim_updates",
                ],
                "review_axes": [
                    "fairness",
                    "data leakage",
                    "metric validity",
                    "reproducibility",
                    "claim evidence alignment",
                ],
            }
        return payload

    def build_result(self, task: Task, ctx, output: dict[str, Any]) -> AgentResult:
        decision = output["decision"]
        next_tasks = []
        status = "success"
        if task.kind == "gap_debate":
            weaknesses = output.get("debate_weaknesses", []) or output.get("blocking_issues", [])
            if self.kb_service is not None and weaknesses:
                for index, weakness in enumerate(weaknesses, start=1):
                    self.kb_service.record_open_question(
                        KnowledgeRecord(
                            record_id=f"open-question:{task.task_id}:{index}",
                            project_id=task.project_id,
                            title=f"Gap debate weakness {index}",
                            summary=str(weakness),
                            context_tags=[task.input_payload.get("gap_id", ""), "gap_debate"],
                            payload={
                                "task_id": task.task_id,
                                "candidate_gap_id": task.input_payload.get("gap_id"),
                                "recommended_constraints": output.get("recommended_constraints", []),
                            },
                        )
                    )
            return AgentResult(
                status="success",
                output={
                    "decision": decision,
                    "summary": output.get("summary", ""),
                    "debate_weaknesses": weaknesses,
                    "recommended_constraints": output.get("recommended_constraints", []),
                },
                audit_notes=output.get("audit_notes", []),
            )
        if decision == "needs_revision":
            status = "handoff"
            if self.kb_service is not None:
                summary = output.get("summary", "")
                for index, issue in enumerate(output.get("blocking_issues", []), start=1):
                    self.kb_service.record_open_question(
                        KnowledgeRecord(
                            record_id=f"open-question:{task.task_id}:{index}",
                            project_id=task.project_id,
                            title=f"Reviewer blocker {index}",
                            summary=str(issue),
                            context_tags=[task.kind, "review_blocker"],
                            payload={"review_summary": summary, "task_id": task.task_id},
                        )
                    )
            next_tasks.append(
                build_child_task(
                    task,
                    kind="implement_experiment",
                    goal="Address reviewer blocking issues",
                    input_payload={
                        "blocking_issues": output.get("blocking_issues", []),
                    },
                    assigned_agent="builder_agent",
                )
            )
        elif decision == "needs_approval":
            status = "needs_approval"
        elif decision == "reject":
            status = "fail"
        else:
            run_id = task.input_payload.get("run_id")
            if isinstance(run_id, str) and run_id:
                next_tasks.append(
                    build_child_task(
                        task,
                        kind="write_draft",
                        goal=f"Write the research draft for {run_id}",
                        input_payload={
                            "run_id": run_id,
                            "claim_ids": task.input_payload.get("claim_ids", []),
                            "artifact_ids": task.input_payload.get("artifact_ids", []),
                        },
                        assigned_agent="writer_agent",
                    )
                )

        return AgentResult(
            status=status,
            output={
                "decision": decision,
                "summary": output.get("summary", ""),
                "blocking_issues": output.get("blocking_issues", []),
                "claim_updates": output.get("claim_updates", []),
            },
            next_tasks=next_tasks,
            audit_notes=output.get("audit_notes", []),
        )
