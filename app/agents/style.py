from __future__ import annotations

from typing import Any

from app.agents.llm_agent import PromptDrivenAgent
from app.agents.response_schemas import STYLE_RESPONSE_SCHEMA
from app.agents.utils import write_artifact
from app.schemas.result import AgentResult
from app.schemas.task import Task
from app.services.artifact_service import ArtifactService


class StyleAgent(PromptDrivenAgent):
    name = "style_agent"
    description = "Polishes language while preserving factual meaning."
    prompt_path = "C:/Anti Project/ResearchOS/prompts/style.md"

    def __init__(
        self,
        provider,
        *,
        artifact_service: ArtifactService | None = None,
        model: str | None = None,
        tool_registry=None,
        provider_registry=None,
        routing_policy=None,
    ) -> None:
        super().__init__(
            provider,
            model=model,
            response_schema=STYLE_RESPONSE_SCHEMA,
            tool_registry=tool_registry,
            provider_registry=provider_registry,
            routing_policy=routing_policy,
        )
        self.artifact_service = artifact_service

    def build_user_payload(self, task, ctx) -> dict[str, Any]:
        payload = super().build_user_payload(task, ctx)
        payload["style_focus"] = {
            "required_outputs": ["revised_markdown", "change_notes"],
            "hard_constraints": [
                "preserve factual meaning",
                "do not soften limitations",
                "make only stylistic changes",
            ],
        }
        return payload

    def build_result(self, task: Task, ctx, output: dict[str, Any]) -> AgentResult:
        artifact = write_artifact(
            run_id=ctx.run_id,
            artifact_id=f"{ctx.run_id}-styled-draft",
            kind="styled_markdown",
            content=output["revised_markdown"],
            extension="md",
            metadata={"source_task_id": task.task_id},
        )
        if self.artifact_service is not None:
            self.artifact_service.register_artifact(artifact)

        return AgentResult(
            status="success",
            output={
                "styled_artifact_path": artifact.path,
                "change_notes": output.get("change_notes", []),
            },
            artifacts=[artifact.artifact_id],
            audit_notes=output.get("change_notes", []),
        )
