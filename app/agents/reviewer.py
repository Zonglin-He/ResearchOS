from __future__ import annotations

from typing import Any

from app.agents.llm_agent import PromptDrivenAgent
from app.agents.response_schemas import REVIEWER_RESPONSE_SCHEMA
from app.agents.utils import build_child_task
from app.roles import reviewer_role_binding
from app.schemas.result import AgentResult
from app.schemas.task import Task


class ReviewerAgent(PromptDrivenAgent):
    name = "reviewer_agent"
    description = "Reviews code, experiments, and claims for validity."
    prompt_path = "prompts/reviewer.md"
    role_binding = reviewer_role_binding()

    def __init__(
        self,
        provider,
        *,
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

    def build_user_payload(self, task, ctx) -> dict[str, Any]:
        payload = super().build_user_payload(task, ctx)
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
        if decision == "needs_revision":
            status = "handoff"
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
