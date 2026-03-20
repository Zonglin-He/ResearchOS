from __future__ import annotations

from typing import Any

from app.agents.llm_agent import PromptDrivenAgent
from app.agents.response_schemas import WRITER_RESPONSE_SCHEMA
from app.agents.utils import build_child_task, write_artifact
from app.roles import writer_role_binding
from app.schemas.result import AgentResult
from app.schemas.task import Task
from app.services.artifact_service import ArtifactService


class WriterAgent(PromptDrivenAgent):
    name = "writer_agent"
    description = "Writes draft sections from frozen evidence."
    prompt_path = "prompts/writer.md"
    role_binding = writer_role_binding()

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
            response_schema=WRITER_RESPONSE_SCHEMA,
            tool_registry=tool_registry,
            provider_registry=provider_registry,
            routing_policy=routing_policy,
            provider_invocation_service=provider_invocation_service,
            role_binding=self.role_binding,
            role_prompt_registry=role_prompt_registry,
            role_skill_registry=role_skill_registry,
        )
        self.artifact_service = artifact_service

    def build_user_payload(self, task, ctx) -> dict[str, Any]:
        payload = super().build_user_payload(task, ctx)
        payload["writer_focus"] = {
            "required_outputs": ["title", "sections", "audit_notes"],
            "hard_constraints": [
                "write only from frozen evidence",
                "do not invent new results",
                "keep claim-evidence alignment explicit",
            ],
        }
        return payload

    def build_result(self, task: Task, ctx, output: dict[str, Any]) -> AgentResult:
        title = output.get("title", "Draft")
        sections = output.get("sections", [])
        markdown = [f"# {title}"]
        for section in sections:
            markdown.append(f"\n## {section['heading']}\n")
            markdown.append(section["markdown"])
        artifact = write_artifact(
            run_id=ctx.run_id,
            artifact_id=f"{ctx.run_id}-draft",
            kind="draft_markdown",
            content="\n".join(markdown).strip() + "\n",
            extension="md",
            metadata={"section_count": len(sections)},
            artifacts_dir=ctx.artifacts_dir or "artifacts",
        )
        if self.artifact_service is not None:
            self.artifact_service.register_artifact(artifact)

        next_tasks = [
            build_child_task(
                task,
                kind="style_pass",
                goal="Polish the draft without changing factual content",
                input_payload={
                    "draft_artifact_path": artifact.path,
                    "title": title,
                },
                assigned_agent="style_agent",
            )
        ]

        return AgentResult(
            status="success",
            output={
                "title": title,
                "sections": sections,
                "draft_artifact_path": artifact.path,
            },
            artifacts=[artifact.artifact_id],
            next_tasks=next_tasks,
            audit_notes=output.get("audit_notes", []),
        )
