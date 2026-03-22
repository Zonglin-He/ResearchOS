from __future__ import annotations

from app.agents.utils import build_child_task
from app.agents.llm_agent import PromptDrivenAgent
from app.agents.response_schemas import ANALYST_RESPONSE_SCHEMA
from app.agents.utils import write_artifact
from app.roles import analyst_role_binding
from app.schemas.result import AgentResult
from app.schemas.task import Task
from app.services.artifact_service import ArtifactService


class AnalystAgent(PromptDrivenAgent):
    name = "analyst_agent"
    description = "Analyzes run outcomes and explains anomalies."
    prompt_path = "prompts/analyst.md"
    role_binding = analyst_role_binding()

    def __init__(
        self,
        provider,
        *,
        artifact_service: ArtifactService | None = None,
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
            response_schema=ANALYST_RESPONSE_SCHEMA,
            tool_registry=tool_registry,
            provider_registry=provider_registry,
            routing_policy=routing_policy,
            provider_invocation_service=provider_invocation_service,
            role_binding=self.role_binding,
            role_prompt_registry=role_prompt_registry,
            role_skill_registry=role_skill_registry,
        )
        self.artifact_service = artifact_service

    def build_result(self, task: Task, ctx, output: dict) -> AgentResult:
        artifact = write_artifact(
            run_id=ctx.run_id,
            artifact_id=f"{ctx.run_id}-result-summary",
            kind="result_summary",
            content=output.get("summary", ""),
            extension="md",
            metadata={
                "anomalies": output.get("anomalies", []),
                "recommended_actions": output.get("recommended_actions", []),
                "role": self.role_binding.resolve_role(task.kind).value,
            },
            artifacts_dir=ctx.artifacts_dir or "artifacts",
        )
        if self.artifact_service is not None:
            self.artifact_service.register_artifact(artifact)
        next_tasks = []
        if task.kind == "analyze_run":
            next_tasks.append(
                build_child_task(
                    task,
                    kind="review_build",
                    goal=f"Review analyzed run outputs for {task.input_payload.get('run_id', ctx.run_id)}",
                    input_payload={
                        "run_id": task.input_payload.get("run_id", ctx.run_id),
                        "artifact_ids": [*task.input_payload.get("artifact_ids", []), artifact.artifact_id],
                        "metrics": output.get("metrics", task.input_payload.get("metrics", {})),
                        "execution_success": output.get(
                            "execution_success",
                            task.input_payload.get("returncode", 1) == 0,
                        ),
                    },
                    assigned_agent="reviewer_agent",
                )
            )
        return AgentResult(
            status="success",
            output={
                "summary": output.get("summary", ""),
                "metrics": output.get("metrics", task.input_payload.get("metrics", {})),
                "execution_success": output.get(
                    "execution_success",
                    task.input_payload.get("returncode", 1) == 0,
                ),
                "anomalies": output.get("anomalies", []),
                "recommended_actions": output.get("recommended_actions", []),
                "result_summary_path": artifact.path,
            },
            artifacts=[artifact.artifact_id],
            next_tasks=next_tasks,
            audit_notes=output.get("audit_notes", []),
        )
