from __future__ import annotations

from typing import Any

from app.agents.llm_agent import PromptDrivenAgent
from app.agents.response_schemas import MAPPER_RESPONSE_SCHEMA
from app.agents.utils import build_child_task
from app.schemas.gap_map import Gap, GapCluster, GapMap
from app.schemas.paper_card import PaperCard
from app.schemas.result import AgentResult
from app.schemas.task import Task
from app.services.gap_map_service import GapMapService
from app.services.paper_card_service import PaperCardService


class MapperAgent(PromptDrivenAgent):
    name = "mapper_agent"
    description = "Maps paper cards into structured gaps and ranked candidates."
    prompt_path = "C:/Anti Project/ResearchOS/prompts/mapper.md"

    def __init__(
        self,
        provider,
        *,
        gap_map_service: GapMapService | None = None,
        paper_card_service: PaperCardService | None = None,
        model: str | None = None,
        tool_registry=None,
        provider_registry=None,
        routing_policy=None,
    ) -> None:
        super().__init__(
            provider,
            model=model,
            response_schema=MAPPER_RESPONSE_SCHEMA,
            tool_registry=tool_registry,
            provider_registry=provider_registry,
            routing_policy=routing_policy,
        )
        self.gap_map_service = gap_map_service
        self.paper_card_service = paper_card_service

    def build_user_payload(self, task, ctx) -> dict[str, Any]:
        payload = super().build_user_payload(task, ctx)
        payload["mapper_focus"] = {
            "required_outputs": ["gap_map", "ranked_candidates", "audit_notes"],
            "do_not_do": ["approve a topic", "use hype language about publication odds"],
        }
        return payload

    def build_result(self, task: Task, ctx, output: dict[str, Any]) -> AgentResult:
        gap_map_payload = output.get("gap_map", {"topic": "", "clusters": []})
        ranked_candidates = output.get("ranked_candidates", [])
        if not gap_map_payload.get("clusters") or not ranked_candidates:
            gap_map_payload, ranked_candidates = self._fallback_gap_map(task)
            output.setdefault(
                "audit_notes",
                [],
            ).append("mapper fallback synthesized a gap map from available paper cards")
        gap_map = self._to_gap_map(gap_map_payload)
        if self.gap_map_service is not None:
            self.gap_map_service.register_gap_map(gap_map)

        next_tasks = []
        if ranked_candidates:
            next_tasks.append(
                build_child_task(
                    task,
                    kind="human_select",
                    goal="Select a promising research direction to freeze",
                    input_payload={
                        "topic": gap_map.topic,
                        "ranked_candidates": ranked_candidates,
                    },
                )
            )

        return AgentResult(
            status="success",
            output={
                "gap_map": gap_map_payload,
                "ranked_candidates": ranked_candidates,
            },
            next_tasks=next_tasks,
            audit_notes=output.get("audit_notes", []),
        )

    @staticmethod
    def _to_gap_map(payload: dict[str, Any]) -> GapMap:
        return GapMap(
            topic=payload.get("topic", ""),
            clusters=[
                GapCluster(
                    name=cluster["name"],
                    gaps=[
                        Gap(
                            gap_id=gap["gap_id"],
                            description=gap["description"],
                            supporting_papers=gap.get("supporting_papers", []),
                            attack_surface=gap.get("attack_surface", ""),
                            difficulty=gap.get("difficulty", ""),
                            novelty_type=gap.get("novelty_type", ""),
                        )
                        for gap in cluster.get("gaps", [])
                    ],
                )
                for cluster in payload.get("clusters", [])
            ],
        )

    def _fallback_gap_map(self, task: Task) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        topic = task.input_payload.get("topic", "research topic")
        cards = self._resolve_cards(task)
        gaps = []
        ranked = []
        for index, card in enumerate(cards, start=1):
            gap_id = f"gap-{index}"
            description = (
                f"Investigate limitations or underexplored extensions around {card.problem or card.title}."
            )
            gaps.append(
                {
                    "gap_id": gap_id,
                    "description": description,
                    "supporting_papers": [card.paper_id],
                    "attack_surface": card.setting,
                    "difficulty": "medium",
                    "novelty_type": "extension",
                }
            )
            ranked.append(
                {
                    "gap_id": gap_id,
                    "score": float(max(1, len(cards) - index + 1)),
                    "rationale": f"Grounded in paper card {card.paper_id} and topic {topic}.",
                }
            )

        if not gaps:
            gaps.append(
                {
                    "gap_id": "gap-1",
                    "description": f"Map open questions for {topic}.",
                    "supporting_papers": task.input_payload.get("paper_ids", []),
                    "attack_surface": topic,
                    "difficulty": "medium",
                    "novelty_type": "open_question",
                }
            )
            ranked.append(
                {
                    "gap_id": "gap-1",
                    "score": 1.0,
                    "rationale": f"Fallback candidate synthesized from topic {topic}.",
                }
            )

        return {
            "topic": topic,
            "clusters": [
                {
                    "name": "Fallback Gap Cluster",
                    "gaps": gaps,
                }
            ],
        }, ranked

    def _resolve_cards(self, task: Task) -> list[PaperCard]:
        payload_cards = task.input_payload.get("paper_cards", [])
        cards = []
        for payload in payload_cards:
            try:
                cards.append(
                    PaperCard(
                        paper_id=payload["paper_id"],
                        title=payload["title"],
                        problem=payload["problem"],
                        setting=payload["setting"],
                        task_type=payload["task_type"],
                    )
                )
            except KeyError:
                continue
        if cards:
            return cards

        if self.paper_card_service is None:
            return []
        resolved = []
        for paper_id in task.input_payload.get("paper_ids", []):
            card = self.paper_card_service.get_card(paper_id)
            if card is not None:
                resolved.append(card)
        return resolved
