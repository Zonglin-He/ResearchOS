from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.agents.orchestrator import Orchestrator
from app.core.enums import Stage
from app.providers.registry import ProviderRegistry
from app.schemas.activity import ConversationMessage, RunEvent
from app.schemas.approval import Approval
from app.schemas.freeze import TopicFreeze
from app.schemas.gap_map import Gap, GapMap
from app.schemas.paper_card import PaperCard
from app.schemas.project import Project
from app.schemas.task import Task, TaskStatus
from app.services.approval_service import ApprovalService
from app.services.activity_service import ActivityService
from app.services.freeze_service import FreezeService
from app.services.gap_map_service import GapMapService
from app.services.paper_card_service import PaperCardService
from app.services.kb_service import KnowledgeBaseService, KnowledgeRecord
from app.services.project_service import ProjectService
from app.services.task_service import TaskService
from app.tools.arxiv_fetcher import search_arxiv
from app.tools.semantic_scholar import search_semantic_scholar, semantic_scholar_score
from app.tools.query_decomposer import fallback_decompose_research_goal, broaden_query, query_hit_count

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DISCUSSION_PROMPT_PATH = _REPO_ROOT / "prompts" / "guide" / "discussion_advisor.md"
_DISCUSSION_SKILL_PATH = _REPO_ROOT / "skills" / "direction-advisor" / "SKILL.md"
_DISCUSSION_RUNTIME_REF_PATH = _REPO_ROOT / "skills" / "direction-advisor" / "references" / "research_checks.md"

_DISCUSSION_PROVIDER = "codex"
_DISCUSSION_MODEL = "gpt-5.4"
_DISCUSSION_REASONING_EFFORT = "high"
_DISCUSSION_VERBOSITY = "medium"
_DISCUSSION_ROLE = "选题顾问"
_DISCUSSION_SKILL = "research-direction-advisor"
_STALE_RUNNING_SHORT_TIMEOUT = timedelta(minutes=30)
_STALE_RUNNING_LONG_TIMEOUT = timedelta(hours=12)


@dataclass(frozen=True)
class AutopilotResult:
    dispatched_task_ids: tuple[str, ...]
    stop_reason: str
    human_select_task_id: str | None = None


@dataclass(frozen=True)
class ResearchStartResult:
    project: Project
    intake_task: Task
    gap_task: Task | None
    autopilot: AutopilotResult


@dataclass(frozen=True)
class IdeaAdoptionResult:
    topic_freeze: TopicFreeze
    build_task: Task
    autopilot: AutopilotResult


@dataclass(frozen=True)
class DirectionDiscussionResult:
    thread_id: str
    assistant_message: str
    gap_id: str
    topic: str
    strengths: tuple[str, ...]
    risks: tuple[str, ...]
    next_checks: tuple[str, ...]
    cited_papers: tuple[str, ...]
    research_question_suggestion: str
    assistant_role: str
    provider_name: str
    model_name: str
    reasoning_effort: str
    skill_name: str


class ResearchGuideService:
    def __init__(
        self,
        *,
        project_service: ProjectService,
        task_service: TaskService,
        freeze_service: FreezeService,
        gap_map_service: GapMapService,
        paper_card_service: PaperCardService,
        provider_registry: ProviderRegistry,
        kb_service: KnowledgeBaseService,
        approval_service: ApprovalService,
        tool_registry,
        orchestrator: Orchestrator,
        activity_service: ActivityService,
    ) -> None:
        self.project_service = project_service
        self.task_service = task_service
        self.freeze_service = freeze_service
        self.gap_map_service = gap_map_service
        self.paper_card_service = paper_card_service
        self.provider_registry = provider_registry
        self.kb_service = kb_service
        self.approval_service = approval_service
        self.tool_registry = tool_registry
        self.orchestrator = orchestrator
        self.activity_service = activity_service
        self._discussion_prompt = _DISCUSSION_PROMPT_PATH.read_text(encoding="utf-8").strip()
        self._discussion_skill = _DISCUSSION_SKILL_PATH.read_text(encoding="utf-8").strip()
        self._discussion_runtime_reference = _DISCUSSION_RUNTIME_REF_PATH.read_text(encoding="utf-8").strip()

    async def start_research(
        self,
        *,
        research_goal: str,
        project_name: str = "",
        project_id: str = "",
        owner: str = "operator",
        keywords: list[str] | None = None,
        max_papers: int = 8,
        expected_min_papers: int = 5,
        auto_dispatch: bool = True,
    ) -> ResearchStartResult:
        goal = research_goal.strip()
        if not goal:
            raise ValueError("research_goal is required")

        resolved_project_name = project_name.strip() or self._suggest_project_name(goal)
        resolved_project_id = self._ensure_unique_project_id(
            project_id.strip() or self._slugify(resolved_project_name or goal, fallback="research-project")
        )
        project = self.project_service.create_project(
            Project(
                project_id=resolved_project_id,
                name=resolved_project_name,
                description=goal,
                status="active",
                stage=Stage.NEW_TOPIC,
            )
        )

        derived_keywords = keywords or self._derive_keywords(goal)
        queries = await self._decompose_queries(goal)
        seed_papers = self._collect_seed_papers(queries, max_papers=max_papers)
        arxiv_query = queries[0] if queries else (" ".join(derived_keywords[:6]) if derived_keywords else goal)
        bootstrap_context = {
            "prior_findings": self.kb_service.search_findings(goal, limit=5, current_project_id=resolved_project_id),
            "prior_decisions": self.kb_service.search_decisions(goal, limit=3, current_project_id=resolved_project_id),
            "prior_literature": self.kb_service.search_bucket("literature", goal, limit=5, current_project_id=resolved_project_id),
            "prior_open_questions": self.kb_service.search_bucket("open_questions", goal, limit=3, current_project_id=resolved_project_id),
            "bootstrap_note": "Use cross-project findings, decisions, literature notes, and open questions as starting context.",
        }
        ingest_tasks: list[Task] = []
        gap_task: Task | None = None
        if seed_papers:
            fanout_group = self._slugify(f"{resolved_project_id}-paper-ingest-fanout", fallback="paper-ingest-fanout")
            planned_paper_ids: list[str] = []
            for index, paper in enumerate(seed_papers[: max(1, max_papers)], start=1):
                source_summary = self._source_summary_from_seed(goal, paper, index=index)
                planned_paper_ids.append(str(source_summary["paper_id"]))
                ingest_tasks.append(
                    self.task_service.create_task(
                        Task(
                            task_id=self._ensure_unique_task_id(f"{resolved_project_id}-paper-ingest-{index:02d}"),
                            project_id=resolved_project_id,
                            kind="paper_ingest",
                            goal=f"Read {source_summary['title']} and distill a durable paper card.",
                            input_payload={
                                "topic": goal,
                                "keywords": derived_keywords,
                                "bootstrap_context": bootstrap_context,
                                "search_query": arxiv_query,
                                "search_source": "arxiv",
                                "source_summary": source_summary,
                                "expected_min_papers": 1,
                                "suppress_next_gap_mapping": True,
                            },
                            owner=owner,
                            fanout_group=fanout_group,
                            join_key="paper_ingest",
                        )
                    )
                )
            gap_task = self.task_service.create_task(
                Task(
                    task_id=self._ensure_unique_task_id(f"{resolved_project_id}-gap-mapping"),
                    project_id=resolved_project_id,
                    kind="gap_mapping",
                    goal=f"Map research gaps for {goal} using the ingested paper cards.",
                    input_payload={
                        "topic": goal,
                        "paper_ids": planned_paper_ids,
                    },
                    owner=owner,
                    depends_on=[task.task_id for task in ingest_tasks],
                    fanout_group=fanout_group,
                    join_key="gap_mapping",
                )
            )
            intake_task = ingest_tasks[0]
        else:
            intake_task = self.task_service.create_task(
                Task(
                    task_id=self._ensure_unique_task_id(f"{resolved_project_id}-paper-ingest"),
                    project_id=resolved_project_id,
                    kind="paper_ingest",
                    goal=f"Research the literature around {goal} and distill durable paper cards.",
                    input_payload={
                        "topic": goal,
                        "keywords": derived_keywords,
                        "bootstrap_context": bootstrap_context,
                        "search_query": arxiv_query,
                        "search_source": "arxiv",
                        "seed_papers": seed_papers,
                        "max_papers": max(1, max_papers),
                        "expected_min_papers": max(1, expected_min_papers),
                    },
                    owner=owner,
                )
            )
            ingest_tasks.append(intake_task)

        self.project_service.update_stage(project.project_id, Stage.INGEST_PAPERS)

        autopilot = AutopilotResult(dispatched_task_ids=tuple(), stop_reason="created")
        self.activity_service.record_event(
            RunEvent(
                project_id=project.project_id,
                task_id=intake_task.task_id,
                event_type="guide.started",
                message=f"Research guide started for project {project.project_id}",
                payload={
                    "research_goal": goal,
                    "project_name": project.name,
                    "search_source": "arxiv",
                    "query_count": len(queries),
                    "seed_paper_count": len(seed_papers),
                    "ingest_task_count": len(ingest_tasks),
                    "gap_task_id": gap_task.task_id if gap_task is not None else None,
                },
            )
        )
        if auto_dispatch:
            autopilot = await self.autopilot_project(resolved_project_id)
        project = self.project_service.get_project(project.project_id) or project
        return ResearchStartResult(project=project, intake_task=intake_task, gap_task=gap_task, autopilot=autopilot)

    async def adopt_direction(
        self,
        *,
        project_id: str,
        human_select_task_id: str,
        gap_id: str,
        research_question: str = "",
        operator_note: str = "",
        novelty_type: list[str] | None = None,
        owner: str = "operator",
        auto_dispatch: bool = True,
    ) -> IdeaAdoptionResult:
        human_select_task = self._require_human_select_task(project_id, human_select_task_id)
        candidate = self._require_candidate(human_select_task, gap_id)

        topic = str(human_select_task.input_payload.get("topic", "")).strip() or project_id
        novelty = [item for item in (novelty_type or []) if item] or ["extension"]
        resolved_question = research_question.strip() or self._build_research_question(topic, gap_id, candidate)
        topic_id = self._slugify(f"{project_id}-{gap_id}-topic", fallback="topic-freeze")
        topic_freeze = self.freeze_service.save_topic_freeze(
            TopicFreeze(
                topic_id=topic_id,
                selected_gap_ids=[gap_id],
                research_question=resolved_question,
                novelty_type=novelty,
                owner=owner,
                status="approved",
            )
        )
        self.project_service.update_stage(project_id, Stage.FREEZE_TOPIC)
        self.kb_service.record_decision(
            KnowledgeRecord(
                record_id=f"decision:{project_id}:{gap_id}",
                project_id=project_id,
                title=f"Adopted direction {gap_id}",
                summary=resolved_question,
                context_tags=[topic, gap_id, *novelty],
                payload={"candidate": candidate, "operator_note": operator_note.strip()},
            )
        )

        if human_select_task.status != TaskStatus.SUCCEEDED:
            human_select_task.status = TaskStatus.SUCCEEDED
            self.task_service.save_task(human_select_task)

        spec_id = self._slugify(f"{topic_id}-spec", fallback="spec-freeze")
        build_task = self.task_service.create_task(
            Task(
                task_id=self._ensure_unique_task_id(f"{project_id}-branch-plan-{gap_id}"),
                project_id=project_id,
                kind="branch_plan",
                goal=f"Plan and explore experiment branches for the selected direction {gap_id} in {topic}.",
                input_payload={
                    "topic": topic,
                    "topic_id": topic_id,
                    "spec_id": spec_id,
                    "selected_gap_id": gap_id,
                    "selected_candidate": candidate,
                    "research_question": resolved_question,
                    "operator_note": operator_note.strip(),
                    "novelty_type": novelty,
                    "target_venue": "NeurIPS",
                },
                owner=owner,
                depends_on=[human_select_task.task_id],
                fanout_group=f"{project_id}:{gap_id}:branching",
                join_key="branch_plan",
            )
        )
        self.project_service.update_stage(project_id, Stage.IMPLEMENT_IDEA)

        autopilot = AutopilotResult(dispatched_task_ids=tuple(), stop_reason="created")
        self.activity_service.record_event(
            RunEvent(
                project_id=project_id,
                task_id=build_task.task_id,
                event_type="guide.direction_adopted",
                message=f"Direction adopted: {gap_id}",
                payload={
                    "human_select_task_id": human_select_task.task_id,
                    "gap_id": gap_id,
                    "topic_id": topic_id,
                    "research_question": resolved_question,
                },
            )
        )
        if auto_dispatch:
            autopilot = await self.autopilot_project(project_id)
        return IdeaAdoptionResult(topic_freeze=topic_freeze, build_task=build_task, autopilot=autopilot)

    async def discuss_direction(
        self,
        *,
        project_id: str,
        human_select_task_id: str,
        gap_id: str,
        user_message: str = "",
        history: list[dict[str, str]] | None = None,
    ) -> DirectionDiscussionResult:
        human_select_task = self._require_human_select_task(project_id, human_select_task_id)
        topic = str(human_select_task.input_payload.get("topic", "")).strip() or project_id
        thread_id = self.activity_service.discussion_thread_id(
            human_select_task_id=human_select_task_id,
            gap_id=gap_id,
        )
        gap_map = self.gap_map_service.get_gap_map(topic)
        gap = self._find_gap(gap_map, gap_id)
        if gap is None:
            raise ValueError(f"gap_id not found in current gap map: {gap_id}")

        candidate = self._require_candidate(human_select_task, gap_id)
        paper_cards = self._supporting_cards(gap)
        known_citations = self._paper_citation_labels(paper_cards)
        persisted_history = [
            {"role": item.role, "content": item.content}
            for item in self.activity_service.list_conversation_messages(
                project_id=project_id,
                thread_id=thread_id,
            )
        ]
        normalized_history = persisted_history or self._normalize_history(history)
        normalized_user_message = user_message.strip()

        if normalized_user_message:
            self.activity_service.record_conversation_message(
                ConversationMessage(
                    project_id=project_id,
                    thread_id=thread_id,
                    human_select_task_id=human_select_task_id,
                    gap_id=gap_id,
                    role="user",
                    content=normalized_user_message,
                )
            )
            self.activity_service.record_event(
                RunEvent(
                    project_id=project_id,
                    task_id=human_select_task_id,
                    event_type="conversation.message",
                    message=f"Operator replied in discussion thread {thread_id}",
                    payload={"thread_id": thread_id, "gap_id": gap_id, "role": "user"},
                )
            )

        response_schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "assistant_message": {"type": "string"},
                "strengths": {"type": "array", "items": {"type": "string"}},
                "risks": {"type": "array", "items": {"type": "string"}},
                "next_checks": {"type": "array", "items": {"type": "string"}},
                "cited_papers": {"type": "array", "items": {"type": "string"}},
                "research_question_suggestion": {"type": "string"},
            },
            "required": [
                "assistant_message",
                "strengths",
                "risks",
                "next_checks",
                "cited_papers",
                "research_question_suggestion",
            ],
        }

        provider = self.provider_registry.get(_DISCUSSION_PROVIDER)
        payload = {
            "mode": "direction_discussion",
            "operator_goal": "Help the operator decide whether this candidate idea should be adopted and frozen.",
            "topic": topic,
            "gap": {
                "gap_id": gap.gap_id,
                "description": gap.description,
                "attack_surface": gap.attack_surface,
                "difficulty": gap.difficulty,
                "novelty_type": gap.novelty_type,
                "supporting_papers": gap.supporting_papers,
            },
            "candidate": candidate,
            "paper_cards": [self._paper_card_payload(card) for card in paper_cards],
            "known_citations": known_citations,
            "conversation_history": normalized_history[-10:],
            "latest_user_message": normalized_user_message,
            "output_language": "zh-Hans",
        }
        system_prompt = self._build_discussion_system_prompt()

        raw = await provider.generate(
            system_prompt=system_prompt,
            user_input=json.dumps(payload, ensure_ascii=False, indent=2),
            response_schema=response_schema,
            model=_DISCUSSION_MODEL,
            provider_config={
                "model_reasoning_effort": _DISCUSSION_REASONING_EFFORT,
                "model_verbosity": _DISCUSSION_VERBOSITY,
            },
        )

        assistant_message = self._clean_text(raw.get("assistant_message")) or self._fallback_assistant_message(
            topic=topic,
            gap=gap,
            cited_papers=known_citations,
        )
        strengths = self._normalize_bullet_list(raw.get("strengths"))
        risks = self._normalize_bullet_list(raw.get("risks"))
        next_checks = self._normalize_bullet_list(raw.get("next_checks"))
        cited_papers = self._normalize_citations(raw.get("cited_papers"), known_citations)
        suggested_question = self._clean_text(raw.get("research_question_suggestion")) or self._build_research_question(
            topic,
            gap_id,
            candidate,
        )
        self.activity_service.record_conversation_message(
            ConversationMessage(
                project_id=project_id,
                thread_id=thread_id,
                human_select_task_id=human_select_task_id,
                gap_id=gap_id,
                role="assistant",
                content=assistant_message,
                metadata={
                    "provider_name": _DISCUSSION_PROVIDER,
                    "model_name": _DISCUSSION_MODEL,
                    "reasoning_effort": _DISCUSSION_REASONING_EFFORT,
                    "research_question_suggestion": suggested_question,
                    "strengths": strengths,
                    "risks": risks,
                    "next_checks": next_checks,
                    "cited_papers": cited_papers,
                    "assistant_role": _DISCUSSION_ROLE,
                    "skill_name": _DISCUSSION_SKILL,
                    "topic": topic,
                },
            )
        )
        self.activity_service.record_event(
            RunEvent(
                project_id=project_id,
                task_id=human_select_task_id,
                event_type="conversation.message",
                message=f"Advisor responded in discussion thread {thread_id}",
                payload={"thread_id": thread_id, "gap_id": gap_id, "role": "assistant"},
            )
        )

        return DirectionDiscussionResult(
            thread_id=thread_id,
            assistant_message=assistant_message,
            gap_id=gap_id,
            topic=topic,
            strengths=tuple(strengths),
            risks=tuple(risks),
            next_checks=tuple(next_checks),
            cited_papers=tuple(cited_papers),
            research_question_suggestion=suggested_question,
            assistant_role=_DISCUSSION_ROLE,
            provider_name=_DISCUSSION_PROVIDER,
            model_name=_DISCUSSION_MODEL,
            reasoning_effort=_DISCUSSION_REASONING_EFFORT,
            skill_name=_DISCUSSION_SKILL,
        )

    async def autopilot_project(self, project_id: str, *, max_dispatches: int = 8) -> AutopilotResult:
        dispatched: list[str] = []
        project = self.project_service.get_project(project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")

        while len(dispatched) < max_dispatches:
            self._recover_stale_running_tasks(project_id)
            tasks = self._project_tasks(project_id)
            checkpoint_stop = self._pending_required_checkpoint(project)
            if checkpoint_stop is not None:
                return AutopilotResult(
                    dispatched_task_ids=tuple(dispatched),
                    stop_reason="waiting_approval",
                )
            human_select_task = self._first_active_human_select(tasks)
            if human_select_task is not None:
                self.project_service.update_stage(project_id, Stage.HUMAN_SELECT)
                return AutopilotResult(
                    dispatched_task_ids=tuple(dispatched),
                    stop_reason="human_select_ready",
                    human_select_task_id=human_select_task.task_id,
                )

            next_batch = self._next_autopilot_batch(
                project_id,
                tasks,
                limit=max_dispatches - len(dispatched),
            )
            if not next_batch:
                return AutopilotResult(
                    dispatched_task_ids=tuple(dispatched),
                    stop_reason=self._idle_reason(tasks),
                )

            self._sync_stage_for_batch(project_id, next_batch)
            results = await asyncio.gather(
                *(self.orchestrator.dispatch(task.task_id) for task in next_batch)
            )
            dispatched.extend(task.task_id for task in next_batch)
            for dispatch in results:
                if dispatch.task.status in {
                    TaskStatus.BLOCKED,
                    TaskStatus.FAILED,
                    TaskStatus.WAITING_APPROVAL,
                }:
                    self._sync_stage_after_dispatch(dispatch.task)
                    return AutopilotResult(
                        dispatched_task_ids=tuple(dispatched),
                        stop_reason=dispatch.task.status.value,
                    )
                self._sync_stage_after_dispatch(dispatch.task)
                project = self.project_service.get_project(project_id) or project
                if self._maybe_create_required_checkpoint(project, dispatch.task):
                    return AutopilotResult(
                        dispatched_task_ids=tuple(dispatched),
                        stop_reason="waiting_approval",
                    )

        return AutopilotResult(
            dispatched_task_ids=tuple(dispatched),
            stop_reason="dispatch_limit_reached",
        )

    def _build_discussion_system_prompt(self) -> str:
        return "\n\n".join(
            [
                self._discussion_prompt,
                "<installed_skill>\n" + self._discussion_skill + "\n</installed_skill>",
                "<runtime_reference>\n" + self._discussion_runtime_reference + "\n</runtime_reference>",
                "<agent_identity>\n"
                f"provider={_DISCUSSION_PROVIDER}\n"
                f"model={_DISCUSSION_MODEL}\n"
                f"reasoning_effort={_DISCUSSION_REASONING_EFFORT}\n"
                f"assistant_role={_DISCUSSION_ROLE}\n"
                f"skill_name={_DISCUSSION_SKILL}\n"
                "</agent_identity>",
            ]
        )

    async def _decompose_queries(self, goal: str) -> list[str]:
        try:
            decomposer = self.tool_registry.get("query_decomposer")
        except KeyError:
            return fallback_decompose_research_goal(goal)
        try:
            result = await decomposer.execute(goal=goal, min_papers_per_query=3)
            queries = [str(item).strip() for item in result.get("queries", []) if str(item).strip()]
        except Exception:
            queries = fallback_decompose_research_goal(goal)
        validated: list[str] = []
        for query in queries[:6]:
            candidate = query.strip()
            if not candidate:
                continue
            attempts = 0
            while attempts < 3 and query_hit_count(candidate) < 3:
                broadened = broaden_query(candidate)
                if not broadened or broadened == candidate:
                    break
                candidate = broadened
                attempts += 1
            if candidate not in validated:
                validated.append(candidate)
        return validated[:6] or fallback_decompose_research_goal(goal)

    @staticmethod
    def _paper_seed_key(item: dict[str, Any]) -> str:
        return str(item.get("doi") or item.get("arxiv_id") or item.get("title") or "").strip().lower()

    def _collect_seed_papers(self, queries: list[str], *, max_papers: int) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        seen: set[str] = set()
        per_query = max(2, min(5, max_papers))
        for query in queries[:6]:
            candidates: list[dict[str, Any]] = []
            try:
                candidates.extend(search_semantic_scholar(query, limit=per_query))
            except Exception:
                pass
            try:
                candidates.extend(search_arxiv(query, max_results=per_query))
            except Exception:
                pass
            candidates.sort(
                key=lambda item: (
                    semantic_scholar_score(item),
                    str(item.get("year") or item.get("published") or ""),
                    str(item.get("title") or ""),
                ),
                reverse=True,
            )
            for item in candidates:
                key = self._paper_seed_key(item)
                if not key or key in seen:
                    continue
                seen.add(key)
                merged.append(item)
                if len(merged) >= max_papers:
                    return merged
        return merged[:max_papers]

    def _pending_required_checkpoint(self, project: Project) -> Approval | None:
        checkpoints = self._human_checkpoints(project)
        if not checkpoints:
            return None
        pending = [
            approval
            for approval in self.approval_service.list_pending()
            if approval.project_id == project.project_id and approval.target_type == "stage_checkpoint"
        ]
        if not pending:
            return None
        active_targets = {f"{project.project_id}:{stage}" for stage, mode in checkpoints.items() if mode == "required"}
        for approval in pending:
            if approval.target_id in active_targets:
                return approval
        return None

    def _maybe_create_required_checkpoint(self, project: Project, task: Task) -> bool:
        checkpoints = self._human_checkpoints(project)
        if not checkpoints:
            return False
        stage = self._stage_for_task_kind(task.kind, terminal_status=task.status)
        if stage is None or stage == Stage.HUMAN_SELECT:
            return False
        mode = checkpoints.get(stage.value, "")
        if mode != "required":
            return False
        target_id = f"{project.project_id}:{stage.value}"
        latest = self.approval_service.latest_target_approval(
            project_id=project.project_id,
            target_type="stage_checkpoint",
            target_id=target_id,
        )
        if latest is not None and latest.decision != "expired":
            return latest.decision == "pending"
        approval = Approval(
            approval_id=f"approval:{target_id}",
            project_id=project.project_id,
            target_type="stage_checkpoint",
            target_id=target_id,
            approved_by="system",
            decision="pending",
            comment=f"Human checkpoint required before leaving stage {stage.value}.",
            context_summary=task.goal,
            recommended_action=f"Review outputs from {task.kind} before continuing autopilot.",
            due_at=datetime.now(timezone.utc) + timedelta(days=7),
        )
        self.approval_service.record_approval(approval)
        return True

    @staticmethod
    def _human_checkpoints(project: Project) -> dict[str, str]:
        dispatch_profile = project.dispatch_profile
        if dispatch_profile is None:
            return {}
        metadata = dispatch_profile.metadata if isinstance(dispatch_profile.metadata, dict) else {}
        checkpoints = metadata.get("human_checkpoints", {})
        if not isinstance(checkpoints, dict):
            return {}
        normalized: dict[str, str] = {}
        for stage, mode in checkpoints.items():
            stage_name = str(stage).strip().upper()
            checkpoint_mode = str(mode).strip().lower()
            if not stage_name or checkpoint_mode not in {"required", "optional"}:
                continue
            normalized[stage_name] = checkpoint_mode
        return normalized

    def _require_human_select_task(self, project_id: str, human_select_task_id: str) -> Task:
        human_select_task = self.task_service.get_task(human_select_task_id)
        if human_select_task is None:
            raise KeyError(f"Task not found: {human_select_task_id}")
        if human_select_task.project_id != project_id:
            raise ValueError("human_select task does not belong to the selected project")
        if human_select_task.kind != "human_select":
            raise ValueError("Only human_select tasks can be discussed or adopted through the guide flow")
        return human_select_task

    @staticmethod
    def _require_candidate(task: Task, gap_id: str) -> dict[str, Any]:
        ranked_candidates = task.input_payload.get("ranked_candidates", [])
        if not isinstance(ranked_candidates, list):
            ranked_candidates = []
        candidate = next(
            (
                item
                for item in ranked_candidates
                if isinstance(item, dict) and str(item.get("gap_id", "")).strip() == gap_id
            ),
            None,
        )
        if candidate is None:
            raise ValueError(f"gap_id not found in ranked_candidates: {gap_id}")
        return candidate

    def _supporting_cards(self, gap: Gap) -> list[PaperCard]:
        cards: list[PaperCard] = []
        for paper_id in gap.supporting_papers:
            card = self.paper_card_service.get_card(paper_id)
            if card is not None:
                cards.append(card)
        return cards

    @staticmethod
    def _paper_card_payload(card: PaperCard) -> dict[str, Any]:
        return {
            "paper_id": card.paper_id,
            "title": card.title,
            "problem": card.problem,
            "setting": card.setting,
            "task_type": card.task_type,
            "method_summary": card.method_summary,
            "datasets": card.datasets,
            "metrics": card.metrics,
            "strongest_result": card.strongest_result,
            "claimed_contributions": card.claimed_contributions,
            "repro_risks": card.repro_risks,
            "likely_failure_modes": card.likely_failure_modes,
            "idea_seeds": card.idea_seeds,
        }

    @staticmethod
    def _paper_citation_labels(cards: list[PaperCard]) -> list[str]:
        labels: list[str] = []
        for card in cards:
            labels.append(card.title)
            labels.append(card.paper_id)
        # Stable order, no duplicates.
        seen: set[str] = set()
        ordered: list[str] = []
        for label in labels:
            if not label or label in seen:
                continue
            seen.add(label)
            ordered.append(label)
        return ordered

    @staticmethod
    def _normalize_history(history: list[dict[str, str]] | None) -> list[dict[str, str]]:
        normalized: list[dict[str, str]] = []
        for entry in history or []:
            if not isinstance(entry, dict):
                continue
            role = str(entry.get("role", "")).strip().lower()
            content = str(entry.get("content", "")).strip()
            if role not in {"user", "assistant"} or not content:
                continue
            normalized.append({"role": role, "content": content})
        return normalized[-8:]

    @staticmethod
    def _clean_text(value: Any) -> str:
        return str(value).strip() if isinstance(value, str) else ""

    @classmethod
    def _normalize_bullet_list(cls, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        normalized: list[str] = []
        for item in value:
            text = cls._clean_text(item)
            if text and text not in normalized:
                normalized.append(text)
        return normalized[:4]

    @staticmethod
    def _normalize_citations(value: Any, known_citations: list[str]) -> list[str]:
        if not isinstance(value, list):
            return known_citations[:4]
        allowed = set(known_citations)
        normalized: list[str] = []
        for item in value:
            label = str(item).strip()
            if label in allowed and label not in normalized:
                normalized.append(label)
        return normalized[:4] or known_citations[:4]

    @staticmethod
    def _fallback_assistant_message(*, topic: str, gap: Gap, cited_papers: list[str]) -> str:
        citations = "、".join(cited_papers[:2]) if cited_papers else "当前证据集"
        return (
            f"这个方向想回答的是：{gap.description}。它目前主要建立在 {citations} 上。"
            f"如果你准备继续，我建议先把研究问题收紧成一个能在单轮实验里验证的命题，再进入 topic freeze。"
        )

    def _project_tasks(self, project_id: str) -> list[Task]:
        return [task for task in self.task_service.list_tasks() if task.project_id == project_id]

    def _recover_stale_running_tasks(self, project_id: str) -> None:
        tasks = self._project_tasks(project_id)
        running_tasks = [task for task in tasks if task.status == TaskStatus.RUNNING]
        if not running_tasks:
            return

        latest_event_times = self.activity_service.latest_task_event_times(
            project_id,
            task_ids=[task.task_id for task in running_tasks],
        )
        now = datetime.now(timezone.utc)
        for task in running_tasks:
            last_seen_at = latest_event_times.get(task.task_id, task.created_at)
            stale_timeout = self._stale_running_timeout(task)
            if now - last_seen_at < stale_timeout:
                continue
            elapsed = now - last_seen_at
            reason = (
                f"Recovered stale running task after {self._format_duration(elapsed)} without new events."
            )
            self.task_service.recover_stale_running_task(task.task_id, reason=reason)

    @staticmethod
    def _stale_running_timeout(task: Task) -> timedelta:
        long_running_markers = ("run", "experiment", "train", "eval")
        if any(marker in task.kind.lower() for marker in long_running_markers):
            return _STALE_RUNNING_LONG_TIMEOUT
        return _STALE_RUNNING_SHORT_TIMEOUT

    @staticmethod
    def _format_duration(delta: timedelta) -> str:
        total_seconds = max(0, int(delta.total_seconds()))
        hours, remainder = divmod(total_seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        if hours > 0:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"

    def list_discussion_messages(
        self,
        *,
        project_id: str,
        human_select_task_id: str,
        gap_id: str,
    ) -> list[ConversationMessage]:
        thread_id = self.activity_service.discussion_thread_id(
            human_select_task_id=human_select_task_id,
            gap_id=gap_id,
        )
        return self.activity_service.list_conversation_messages(project_id=project_id, thread_id=thread_id)

    @staticmethod
    def _find_gap(gap_map: GapMap | None, gap_id: str) -> Gap | None:
        if gap_map is None:
            return None
        for cluster in gap_map.clusters:
            for gap in cluster.gaps:
                if gap.gap_id == gap_id:
                    return gap
        return None

    @staticmethod
    def _first_active_human_select(tasks: list[Task]) -> Task | None:
        for task in sorted(tasks, key=lambda item: item.created_at):
            if task.kind != "human_select":
                continue
            if task.status in {TaskStatus.CANCELLED, TaskStatus.SUCCEEDED}:
                continue
            return task
        return None

    def _next_autopilot_batch(
        self,
        project_id: str,
        tasks: list[Task],
        *,
        limit: int,
    ) -> list[Task]:
        runnable = self.task_service.list_runnable_tasks(project_id=project_id)
        ordered = {task.task_id: task for task in sorted(tasks, key=lambda item: item.created_at)}
        ordered_runnable = [
            ordered[task.task_id]
            for task in runnable
            if task.task_id in ordered and task.kind != "human_select"
        ]
        if not ordered_runnable:
            return []

        first = ordered_runnable[0]
        if first.fanout_group:
            batch = [
                task
                for task in ordered_runnable
                if task.fanout_group == first.fanout_group and task.kind == first.kind
            ]
            return batch[:limit]

        for task in ordered_runnable:
            if task.kind == "human_select":
                continue
            return [task]
        return []

    def _sync_stage_for_batch(self, project_id: str, tasks: list[Task]) -> None:
        if not tasks:
            return
        stage = self._stage_for_task_kind(tasks[0].kind)
        if stage is not None:
            self.project_service.update_stage(project_id, stage)

    def _sync_stage_after_dispatch(self, task: Task) -> None:
        stage = self._stage_for_task_kind(task.kind, terminal_status=task.status)
        if stage is not None:
            self.project_service.update_stage(task.project_id, stage)

    @staticmethod
    def _idle_reason(tasks: list[Task]) -> str:
        if any(task.status == TaskStatus.RUNNING for task in tasks):
            return "running"
        if any(task.status == TaskStatus.WAITING_APPROVAL for task in tasks):
            return "waiting_approval"
        if any(task.status == TaskStatus.BLOCKED for task in tasks):
            return "blocked"
        if any(task.status == TaskStatus.FAILED for task in tasks):
            return "failed"
        return "idle"

    def _ensure_unique_project_id(self, base_id: str) -> str:
        project_id = base_id
        counter = 2
        while self.project_service.get_project(project_id) is not None:
            project_id = f"{base_id}-{counter}"
            counter += 1
        return project_id

    def _ensure_unique_task_id(self, base_id: str) -> str:
        task_id = self._slugify(base_id, fallback="task")
        counter = 2
        while self.task_service.get_task(task_id) is not None:
            task_id = f"{self._slugify(base_id, fallback='task')}-{counter}"
            counter += 1
        return task_id

    @staticmethod
    def _build_research_question(topic: str, gap_id: str, candidate: dict[str, Any]) -> str:
        rationale = str(candidate.get("rationale", "")).strip()
        if rationale:
            return f"Can {gap_id} become a concrete, testable direction for {topic}? Focus on: {rationale}"
        return f"Can {gap_id} become a concrete, testable direction for {topic}?"

    @staticmethod
    def _suggest_project_name(goal: str) -> str:
        cleaned = goal.strip()
        if not cleaned:
            return "ResearchOS Project"
        return cleaned[:80]

    @staticmethod
    def _derive_keywords(goal: str) -> list[str]:
        pieces = re.split(r"[\s,;:/]+", goal)
        cleaned: list[str] = []
        for piece in pieces:
            token = piece.strip()
            if len(token) < 3:
                continue
            if token.lower() in {"the", "and", "for", "with", "into", "from"}:
                continue
            if token not in cleaned:
                cleaned.append(token)
        return cleaned[:6] or [goal]

    @staticmethod
    def _slugify(value: str, *, fallback: str) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.strip().lower()).strip("-")
        return slug[:80] or fallback

    @staticmethod
    def _stage_for_task_kind(
        task_kind: str,
        *,
        terminal_status: TaskStatus | None = None,
    ) -> Stage | None:
        if task_kind == "paper_ingest":
            return Stage.INGEST_PAPERS
        if task_kind == "gap_mapping":
            return Stage.HUMAN_SELECT if terminal_status == TaskStatus.SUCCEEDED else Stage.MAP_GAPS
        if task_kind == "human_select":
            return Stage.FREEZE_TOPIC
        if task_kind in {"build_spec", "implement_experiment", "reproduce_baseline"}:
            return Stage.IMPLEMENT_IDEA if terminal_status != TaskStatus.SUCCEEDED else Stage.RUN_EXPERIMENTS
        if task_kind == "branch_plan":
            return Stage.IMPLEMENT_IDEA if terminal_status != TaskStatus.SUCCEEDED else Stage.RUN_EXPERIMENTS
        if task_kind == "branch_review":
            return Stage.FREEZE_RESULTS if terminal_status == TaskStatus.SUCCEEDED else Stage.RUN_EXPERIMENTS
        if task_kind == "analyze_run":
            return Stage.AUDIT_RESULTS
        if task_kind in {"review_build", "audit_run"}:
            return Stage.REVIEW_DRAFT
        if task_kind == "draft_write":
            return Stage.WRITE_DRAFT
        if task_kind == "style_pass":
            return Stage.SUBMISSION_READY if terminal_status == TaskStatus.SUCCEEDED else Stage.STYLE_PASS
        return None

    @staticmethod
    def _source_summary_from_seed(topic: str, paper: dict[str, Any], *, index: int) -> dict[str, Any]:
        title = str(paper.get("title", "")).strip() or f"{topic} paper {index}"
        arxiv_id = str(paper.get("arxiv_id", "")).strip()
        paper_id = f"arxiv:{arxiv_id}" if arxiv_id else f"seed-paper-{index}"
        authors = [str(author).strip() for author in paper.get("authors", []) if str(author).strip()]
        pdf_url = str(paper.get("pdf_url", "")).strip()
        published = str(paper.get("published", "")).strip()
        abstract = str(paper.get("abstract", "")).strip()
        strongest_result = ""
        if published:
            strongest_result = f"Published on {published}."
        return {
            "paper_id": paper_id,
            "title": title,
            "abstract": abstract,
            "setting": topic,
            "task_type": topic,
            "datasets": [],
            "metrics": [],
            "strongest_result": strongest_result,
            "claimed_contributions": authors[:4] + ([pdf_url] if pdf_url else []),
        }
