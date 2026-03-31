from __future__ import annotations

from dataclasses import dataclass

from app.schemas.memory import MemoryRecord
from app.schemas.project import Project
from app.schemas.strategy import RetrievalEvidence, StrategyTrace
from app.schemas.task import Task
from app.services.memory_registry_service import MemoryRegistryService


@dataclass(frozen=True)
class StrategyDecision:
    trace: StrategyTrace
    evidence: tuple[RetrievalEvidence, ...] = ()


class StrategyService:
    def __init__(self, memory_registry: MemoryRegistryService) -> None:
        self.memory_registry = memory_registry

    def decide(self, *, task: Task, project: Project | None = None) -> StrategyDecision:
        retrieval_targets = self._retrieval_targets(task)
        should_retrieve = bool(retrieval_targets)
        tool_candidates = self._tool_candidates(task)
        should_call_tools = bool(tool_candidates)
        needs_human_checkpoint = task.kind in {"human_select", "branch_review", "write_draft"}
        reasoning_summary = self._reasoning_summary(
            task=task,
            retrieval_targets=retrieval_targets,
            tool_candidates=tool_candidates,
            needs_human_checkpoint=needs_human_checkpoint,
        )
        evidence = self._retrieve_evidence(task, retrieval_targets)
        trace = StrategyTrace(
            task_id=task.task_id,
            project_id=task.project_id,
            should_retrieve=should_retrieve,
            retrieval_targets=tuple(retrieval_targets),
            should_call_tools=should_call_tools,
            tool_candidates=tuple(tool_candidates),
            needs_human_checkpoint=needs_human_checkpoint,
            reasoning_summary=reasoning_summary,
        )
        _ = project
        return StrategyDecision(trace=trace, evidence=tuple(evidence))

    def latest_project_strategy(self, *, project_id: str, tasks: list[Task]) -> StrategyTrace | None:
        project_tasks = [
            task
            for task in tasks
            if task.project_id == project_id and task.latest_strategy_trace is not None
        ]
        if not project_tasks:
            return None
        project_tasks.sort(key=lambda item: item.created_at, reverse=True)
        return project_tasks[0].latest_strategy_trace

    def _retrieve_evidence(self, task: Task, retrieval_targets: list[str]) -> list[RetrievalEvidence]:
        query_parts = [
            str(task.input_payload.get("topic", "")).strip(),
            str(task.input_payload.get("research_question", "")).strip(),
            task.goal.strip(),
            task.kind.strip(),
        ]
        query = " ".join(part for part in query_parts if part)
        records = self.memory_registry.search(
            project_id=task.project_id,
            query=query,
            limit=6,
            min_confidence=0.4,
        )
        evidence: list[RetrievalEvidence] = []
        for record in records:
            if retrieval_targets and not self._matches_target(record, retrieval_targets):
                continue
            evidence.append(self._to_evidence(record))
        return evidence

    @staticmethod
    def _matches_target(record: MemoryRecord, retrieval_targets: list[str]) -> bool:
        normalized_bucket = record.bucket.lower()
        return any(target in normalized_bucket for target in retrieval_targets)

    @staticmethod
    def _to_evidence(record: MemoryRecord) -> RetrievalEvidence:
        source_id = record.source_task_id or record.record_id
        return RetrievalEvidence(
            source_type=record.bucket,
            source_id=source_id,
            title=record.metadata.get("title", record.summary[:60]) if isinstance(record.metadata, dict) else record.summary[:60],
            snippet=record.summary,
            score=round(record.confidence, 3),
            why_selected=f"Matched memory bucket {record.bucket} with confidence {record.confidence:.2f}.",
        )

    @staticmethod
    def _retrieval_targets(task: Task) -> list[str]:
        if task.kind in {"paper_ingest", "repo_ingest", "read_source"}:
            return ["retrieval_note", "research_decision"]
        if task.kind in {"gap_mapping", "map_gaps", "gap_debate"}:
            return ["retrieval_note", "working_summary", "research_decision"]
        if task.kind in {"branch_review", "analyze_run", "verify_claim", "verify_results", "write_draft"}:
            return ["execution_lesson", "research_decision", "working_summary"]
        if task.kind == "human_select":
            return ["research_decision", "retrieval_note"]
        return []

    @staticmethod
    def _tool_candidates(task: Task) -> list[str]:
        if task.kind in {"paper_ingest", "repo_ingest"}:
            return ["arxiv_fetcher", "paper_search", "semantic_scholar"]
        if task.kind in {"implement_experiment", "reproduce_baseline", "build_spec"}:
            return ["python_exec", "filesystem", "shell_tool", "experiment_runner"]
        if task.kind in {"verify_claim", "verify_results"}:
            return ["citation_verifier", "filesystem"]
        if task.kind in {"read_source"}:
            return ["pdf_parse", "filesystem"]
        return []

    @staticmethod
    def _reasoning_summary(
        *,
        task: Task,
        retrieval_targets: list[str],
        tool_candidates: list[str],
        needs_human_checkpoint: bool,
    ) -> str:
        parts = [f"task kind {task.kind}"]
        if retrieval_targets:
            parts.append(f"retrieval from {', '.join(retrieval_targets)}")
        if tool_candidates:
            parts.append(f"tool candidates {', '.join(tool_candidates)}")
        if needs_human_checkpoint:
            parts.append("human checkpoint recommended")
        return "; ".join(parts)
