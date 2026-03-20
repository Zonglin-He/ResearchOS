from __future__ import annotations

from typing import Any

from app.agents.llm_agent import PromptDrivenAgent
from app.agents.response_schemas import WRITER_RESPONSE_SCHEMA
from app.agents.utils import build_child_task, write_artifact
from app.schemas.result import AgentResult
from app.schemas.task import Task
from app.services.artifact_service import ArtifactService


class WriterAgent(PromptDrivenAgent):
    name = "writer_agent"
    description = "Writes draft sections from frozen evidence."
    prompt_path = "C:/Anti Project/ResearchOS/prompts/writer.md"

    def __init__(
        self,
        provider,
        *,
        artifact_service: ArtifactService | None = None,
        model: str | None = None,
        tool_registry=None,
    ) -> None:
        super().__init__(
            provider,
            model=model,
            response_schema=WRITER_RESPONSE_SCHEMA,
            tool_registry=tool_registry,
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
