from __future__ import annotations

from app.agents.llm_agent import PromptDrivenAgent
from app.agents.response_schemas import ARCHIVIST_RESPONSE_SCHEMA
from app.agents.utils import write_artifact
from app.roles import archivist_role_binding
from app.schemas.lesson import LessonKind, LessonRecord
from app.schemas.result import AgentResult
from app.schemas.task import Task
from app.services.artifact_service import ArtifactService
from app.services.lessons_service import LessonsService


class ArchivistAgent(PromptDrivenAgent):
    name = "archivist_agent"
    description = "Curates lessons, provenance notes, and archive entries."
    prompt_path = "C:/Anti Project/ResearchOS/prompts/archivist.md"
    role_binding = archivist_role_binding()

    def __init__(
        self,
        provider,
        *,
        lessons_service: LessonsService | None = None,
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
            response_schema=ARCHIVIST_RESPONSE_SCHEMA,
            tool_registry=tool_registry,
            provider_registry=provider_registry,
            routing_policy=routing_policy,
            provider_invocation_service=provider_invocation_service,
            role_binding=self.role_binding,
            role_prompt_registry=role_prompt_registry,
            role_skill_registry=role_skill_registry,
        )
        self.lessons_service = lessons_service
        self.artifact_service = artifact_service

    def build_result(self, task: Task, ctx, output: dict) -> AgentResult:
        lesson_ids: list[str] = []
        if self.lessons_service is not None:
            for index, item in enumerate(output.get("lessons", []), start=1):
                lesson = LessonRecord(
                    lesson_id=f"{task.task_id}:archive:{index}",
                    lesson_kind=LessonKind(item.get("lesson_kind", LessonKind.LESSON.value)),
                    title=item["title"],
                    summary=item["summary"],
                    rationale=output.get("summary", ""),
                    recommended_action=item.get("recommended_action", ""),
                    task_kind=task.kind,
                    agent_name=self.name,
                    provider_name=ctx.routing.provider_name if ctx.routing is not None else None,
                    model_name=ctx.routing.model if ctx.routing is not None else None,
                    failure_type=item.get("failure_type"),
                    evidence_refs=item.get("evidence_refs", []),
                    source_task_id=task.task_id,
                )
                self.lessons_service.record_lesson(lesson)
                lesson_ids.append(lesson.lesson_id)

        content = "\n".join(
            [
                "# Archive Entry",
                "",
                output.get("summary", ""),
                "",
                "## Provenance Notes",
                *[f"- {note}" for note in output.get("provenance_notes", [])],
            ]
        ).strip() + "\n"
        artifact = write_artifact(
            run_id=ctx.run_id,
            artifact_id=f"{ctx.run_id}-archive-entry",
            kind="archive_entry",
            content=content,
            extension="md",
            metadata={"lesson_ids": lesson_ids},
            artifacts_dir=ctx.artifacts_dir or "artifacts",
        )
        if self.artifact_service is not None:
            self.artifact_service.register_artifact(artifact)

        return AgentResult(
            status="success",
            output={
                "summary": output.get("summary", ""),
                "lesson_ids": lesson_ids,
                "archive_entry_path": artifact.path,
            },
            artifacts=[artifact.artifact_id],
            audit_notes=output.get("audit_notes", []),
        )
