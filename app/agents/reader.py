from __future__ import annotations

from typing import Any

from app.agents.llm_agent import PromptDrivenAgent
from app.agents.response_schemas import READER_RESPONSE_SCHEMA
from app.agents.utils import build_child_task
from app.roles import reader_role_binding
from app.schemas.artifact import ArtifactRecord
from app.schemas.paper_card import EvidenceRef, PaperCard
from app.schemas.result import AgentResult
from app.schemas.task import Task
from app.services.artifact_service import ArtifactService
from app.services.paper_card_service import PaperCardService


class ReaderAgent(PromptDrivenAgent):
    name = "reader_agent"
    description = "Reads papers and repositories into structured research artifacts."
    prompt_path = "prompts/reader.md"
    role_binding = reader_role_binding()

    def __init__(
        self,
        provider,
        *,
        paper_card_service: PaperCardService | None = None,
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
            response_schema=READER_RESPONSE_SCHEMA,
            tool_registry=tool_registry,
            provider_registry=provider_registry,
            routing_policy=routing_policy,
            provider_invocation_service=provider_invocation_service,
            role_binding=self.role_binding,
            role_prompt_registry=role_prompt_registry,
            role_skill_registry=role_skill_registry,
        )
        self.paper_card_service = paper_card_service
        self.artifact_service = artifact_service

    def build_user_payload(self, task, ctx) -> dict[str, Any]:
        payload = super().build_user_payload(task, ctx)
        payload["reader_focus"] = {
            "required_outputs": [
                "paper_cards",
                "artifact_notes",
                "uncertainties",
                "audit_notes",
            ],
            "do_not_do": [
                "approve a research direction",
                "state unsupported facts as certain",
            ],
            "minimum_expectation": (
                "If task.input_payload contains source_summary, produce at least one "
                "PaperCard from that summary instead of leaving paper_cards empty."
            ),
        }
        return payload

    def build_result(self, task: Task, ctx, output: dict[str, Any]) -> AgentResult:
        raw_cards = output.get("paper_cards", [])
        if not raw_cards:
            fallback_card = self._fallback_paper_card(task)
            if fallback_card is not None:
                raw_cards = [fallback_card]
                output.setdefault(
                    "audit_notes",
                    [],
                ).append("reader fallback synthesized a paper card from source_summary")

        paper_cards = [self._to_paper_card(item) for item in raw_cards]
        for card in paper_cards:
            if self.paper_card_service is not None:
                self.paper_card_service.register_card(card)

        artifacts = []
        for index, note in enumerate(output.get("artifact_notes", []), start=1):
            artifact = ArtifactRecord(
                artifact_id=f"{ctx.run_id}-reader-note-{index}",
                run_id=ctx.run_id,
                kind="reader_note",
                path="",
                hash="",
                metadata={"note": note},
            )
            if self.artifact_service is not None:
                self.artifact_service.register_artifact(artifact)
            artifacts.append(artifact.artifact_id)

        next_tasks = []
        if paper_cards:
            next_tasks.append(
                build_child_task(
                    task,
                    kind="gap_mapping",
                    goal=f"Map research gaps for project {task.project_id}",
                    input_payload={
                        "paper_ids": [card.paper_id for card in paper_cards],
                        "topic": task.input_payload.get("topic", ""),
                    },
                    assigned_agent="mapper_agent",
                )
            )

        return AgentResult(
            status="success",
            output={
                "paper_cards": raw_cards,
                "uncertainties": output.get("uncertainties", []),
            },
            artifacts=artifacts,
            next_tasks=next_tasks,
            audit_notes=output.get("audit_notes", []),
        )

    @staticmethod
    def _to_paper_card(payload: dict[str, Any]) -> PaperCard:
        return PaperCard(
            paper_id=payload["paper_id"],
            title=payload["title"],
            problem=payload["problem"],
            setting=payload["setting"],
            task_type=payload["task_type"],
            core_assumption=payload.get("core_assumption", []),
            method_summary=payload.get("method_summary", ""),
            key_modules=payload.get("key_modules", []),
            datasets=payload.get("datasets", []),
            metrics=payload.get("metrics", []),
            strongest_result=payload.get("strongest_result", ""),
            claimed_contributions=payload.get("claimed_contributions", []),
            hidden_dependencies=payload.get("hidden_dependencies", []),
            likely_failure_modes=payload.get("likely_failure_modes", []),
            repro_risks=payload.get("repro_risks", []),
            idea_seeds=payload.get("idea_seeds", []),
            evidence_refs=[
                EvidenceRef(section=ref["section"], page=ref["page"])
                for ref in payload.get("evidence_refs", [])
            ],
        )

    @staticmethod
    def _fallback_paper_card(task: Task) -> dict[str, Any] | None:
        source_summary = task.input_payload.get("source_summary")
        if not isinstance(source_summary, dict):
            return None

        title = source_summary.get("title", task.goal)
        abstract = source_summary.get("abstract", "")
        setting = source_summary.get("setting", "")
        topic = task.input_payload.get("topic", "")
        paper_id = source_summary.get("paper_id") or title.lower().replace(" ", "_")[:32] or task.task_id
        return {
            "paper_id": paper_id,
            "title": title,
            "problem": abstract or f"Research problem around {topic}".strip(),
            "setting": setting or topic or "unspecified setting",
            "task_type": source_summary.get("task_type", topic or "research"),
            "core_assumption": [],
            "method_summary": abstract,
            "key_modules": [],
            "datasets": source_summary.get("datasets", []),
            "metrics": source_summary.get("metrics", []),
            "strongest_result": source_summary.get("strongest_result", ""),
            "claimed_contributions": source_summary.get("claimed_contributions", []),
            "hidden_dependencies": [],
            "likely_failure_modes": [],
            "repro_risks": [],
            "idea_seeds": [topic] if topic else [],
            "evidence_refs": [{"section": "source_summary", "page": 1}],
        }
