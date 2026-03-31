from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class RetrievalEvidence:
    source_type: str
    source_id: str
    title: str
    snippet: str
    score: float
    why_selected: str


@dataclass(frozen=True)
class StrategyTrace:
    task_id: str
    project_id: str
    should_retrieve: bool
    retrieval_targets: tuple[str, ...] = ()
    should_call_tools: bool = False
    tool_candidates: tuple[str, ...] = ()
    needs_human_checkpoint: bool = False
    reasoning_summary: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class HandoffPacket:
    from_agent: str
    to_agent: str
    task_kind: str
    objective: str
    required_inputs: tuple[str, ...] = ()
    attached_evidence_ids: tuple[str, ...] = ()
    blocking_questions: tuple[str, ...] = ()
    done_definition: str = ""
