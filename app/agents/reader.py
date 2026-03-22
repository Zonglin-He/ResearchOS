from __future__ import annotations

from typing import Any

from app.agents.llm_agent import PromptDrivenAgent
from app.agents.response_schemas import READER_RESPONSE_SCHEMA
from app.agents.utils import build_child_task
from app.roles import reader_role_binding
from app.schemas.artifact import ArtifactRecord
from app.schemas.context import RunContext
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

    async def run(self, task: Task, ctx: RunContext) -> AgentResult:
        search_output = await self._search_output(task)
        if search_output is not None:
            result = self.build_result(task, ctx, search_output)
            role_asset_note = self._build_role_asset_audit_note(task)
            if role_asset_note is not None:
                result.audit_notes.append(role_asset_note)
            return result
        return await super().run(task, ctx)

    def build_user_payload(self, task, ctx) -> dict[str, Any]:
        payload = super().build_user_payload(task, ctx)
        arxiv_seeds = task.input_payload.get("arxiv_seeds", [])
        search_seeds = task.input_payload.get("search_seeds", [])
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
            "retrieval_expectation": (
                "If arxiv_seeds or search_seeds are present, treat them as retrieval context "
                "for deeper extraction rather than final paper cards. Use the seeded titles, "
                "abstracts, authors, and identifiers to infer richer datasets, metrics, "
                "modules, and contributions only when grounded in that evidence."
            ),
        }
        if isinstance(arxiv_seeds, list) and arxiv_seeds:
            payload["arxiv_context"] = arxiv_seeds
        if isinstance(search_seeds, list) and search_seeds:
            payload["search_context"] = search_seeds
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

        blocking_reasons = self._blocking_reasons(task, raw_cards, output)
        if blocking_reasons:
            audit_notes = output.get("audit_notes", [])
            audit_notes.extend(f"reader blocked promotion to gap_mapping: {reason}" for reason in blocking_reasons)
            return AgentResult(
                status="handoff",
                output={
                    "paper_cards": raw_cards,
                    "uncertainties": output.get("uncertainties", []),
                    "blocking_reasons": blocking_reasons,
                },
                audit_notes=audit_notes,
            )

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
        suppress_gap_mapping = bool(task.input_payload.get("suppress_next_gap_mapping"))
        if paper_cards and not suppress_gap_mapping:
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

    def _blocking_reasons(
        self,
        task: Task,
        raw_cards: list[dict[str, Any]],
        output: dict[str, Any],
    ) -> list[str]:
        reasons: list[str] = []
        topic = str(task.input_payload.get("topic", "")).strip()
        expected_min = task.input_payload.get("expected_min_papers", 1)
        try:
            min_papers = max(1, int(expected_min))
        except (TypeError, ValueError):
            min_papers = 1

        audit_notes = " ".join(str(note) for note in output.get("audit_notes", [])).lower()
        uncertainties = " ".join(str(note) for note in output.get("uncertainties", [])).lower()

        if len(raw_cards) < min_papers:
            reasons.append(f"expected at least {min_papers} paper cards, received {len(raw_cards)}")
        if "local provider generated deterministic reader output" in audit_notes:
            reasons.append("reader output came from the deterministic local provider placeholder path")
        if "reader fallback synthesized a paper card from source_summary" in audit_notes:
            reasons.append("reader fell back to synthesizing a card from source_summary instead of paper retrieval")
        if "source_summary fallback" in uncertainties:
            reasons.append("reader reported source_summary fallback rather than retrieved paper evidence")
        if raw_cards and all(self._looks_placeholder_card(task, card, topic) for card in raw_cards):
            reasons.append("all returned paper cards look like placeholders rather than retrieved papers")
        return reasons

    @staticmethod
    def _looks_placeholder_card(task: Task, raw_card: dict[str, Any], topic: str) -> bool:
        evidence_refs = raw_card.get("evidence_refs", [])
        source_summary_only = bool(evidence_refs) and all(
            isinstance(ref, dict) and ref.get("section") == "source_summary"
            for ref in evidence_refs
        )
        sparse_content = not any(
            raw_card.get(field)
            for field in (
                "datasets",
                "metrics",
                "claimed_contributions",
                "strongest_result",
                "key_modules",
            )
        )
        title = str(raw_card.get("title", "")).strip().lower()
        goal = str(task.goal).strip().lower()
        normalized_topic = topic.lower()
        generic_title = title == goal or (normalized_topic and normalized_topic in title)
        return source_summary_only and sparse_content and generic_title

    async def _search_output(self, task: Task) -> dict[str, Any] | None:
        if task.kind != "paper_ingest":
            return None
        source_summary = task.input_payload.get("source_summary")
        if isinstance(source_summary, dict):
            fallback_card = self._fallback_paper_card(task)
            if fallback_card is None:
                return None
            return {
                "paper_cards": [fallback_card],
                "artifact_notes": ["paper_ingest used pre-fetched source_summary payload"],
                "uncertainties": [
                    "source_summary came from upstream metadata; detailed dataset or metric fields may still be sparse"
                ],
                "audit_notes": [
                    "reader created a paper card directly from source_summary",
                ],
            }

        seed_papers = task.input_payload.get("seed_papers", [])
        if isinstance(seed_papers, list) and seed_papers:
            task.input_payload["arxiv_seeds"] = [item for item in seed_papers if isinstance(item, dict)]
            return None

        if self.tool_registry is None:
            return None

        query = self._paper_query(task)
        if not query:
            return None

        expected_min = task.input_payload.get("expected_min_papers", 5)
        max_papers = task.input_payload.get("max_papers", expected_min)
        try:
            limit = max(1, int(max_papers))
        except (TypeError, ValueError):
            limit = 5

        try:
            arxiv_tool = self.tool_registry.get("arxiv_fetcher")
        except KeyError:
            arxiv_tool = None

        if arxiv_tool is not None:
            search_result = await arxiv_tool.execute(query=query, max_results=limit)
            items = search_result.get("items", [])
            seeded_items = [item for item in items if item.get("title")]
            if seeded_items:
                task.input_payload["arxiv_seeds"] = seeded_items
                return None

        try:
            search_tool = self.tool_registry.get("paper_search")
        except KeyError:
            return None

        search_result = await search_tool.execute(query=query, limit=limit)
        items = search_result.get("items", [])
        seeded_items = [item for item in items if item.get("title")]
        if seeded_items:
            task.input_payload["search_seeds"] = seeded_items
        return None

    @staticmethod
    def _card_from_arxiv_hit(task: Task, item: dict[str, Any]) -> dict[str, Any]:
        topic = str(task.input_payload.get("topic", "")).strip() or "arXiv search"
        title = str(item.get("title", "")).strip()
        abstract = str(item.get("abstract", "")).strip()
        arxiv_id = str(item.get("arxiv_id", "")).strip()
        published = str(item.get("published", "")).strip()
        authors = [str(author).strip() for author in item.get("authors", []) if str(author).strip()]
        paper_id = f"arxiv:{arxiv_id}" if arxiv_id else title.lower().replace(" ", "_")[:64]
        summary_bits = [
            f"arXiv candidate for {topic}.",
            authors and f"Authors: {', '.join(authors[:4])}.",
            published and f"Published: {published}.",
            item.get("pdf_url") and f"PDF: {item['pdf_url']}.",
        ]
        return {
            "paper_id": paper_id,
            "title": title,
            "problem": abstract or f"Retrieved from arXiv for {topic}.",
            "setting": topic,
            "task_type": topic,
            "core_assumption": [],
            "method_summary": " ".join(bit for bit in summary_bits if bit),
            "key_modules": [],
            "datasets": [],
            "metrics": [],
            "strongest_result": "",
            "claimed_contributions": authors[:4],
            "hidden_dependencies": [],
            "likely_failure_modes": [],
            "repro_risks": [],
            "idea_seeds": [topic],
            "evidence_refs": [{"section": "arxiv", "page": 1}],
        }

    @staticmethod
    def _paper_query(task: Task) -> str:
        keywords = task.input_payload.get("keywords", [])
        if isinstance(keywords, list):
            cleaned = [str(item).strip() for item in keywords if str(item).strip()]
            if cleaned:
                return " ".join(cleaned[:6])
        topic = str(task.input_payload.get("topic", "")).strip()
        if topic:
            return topic
        return str(task.goal).strip()

    @staticmethod
    def _card_from_search_hit(task: Task, item: dict[str, Any]) -> dict[str, Any]:
        topic = str(task.input_payload.get("topic", "")).strip() or "paper search"
        title = str(item.get("title", "")).strip()
        doi = str(item.get("doi", "")).strip()
        published = str(item.get("published", "")).strip()
        paper_id = doi or title.lower().replace(" ", "_")[:64]
        summary_bits = [bit for bit in [f"Crossref hit for {topic}.", doi and f"DOI: {doi}.", published and f"Published: {published}."] if bit]
        return {
            "paper_id": paper_id,
            "title": title,
            "problem": f"Retrieved as a relevant paper for {topic}.",
            "setting": topic,
            "task_type": topic,
            "core_assumption": [],
            "method_summary": " ".join(summary_bits),
            "key_modules": [],
            "datasets": [],
            "metrics": [],
            "strongest_result": "",
            "claimed_contributions": [f"Crossref DOI {doi}"] if doi else [],
            "hidden_dependencies": [],
            "likely_failure_modes": [],
            "repro_risks": [],
            "idea_seeds": [topic],
            "evidence_refs": [{"section": "crossref", "page": 1}],
        }

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
