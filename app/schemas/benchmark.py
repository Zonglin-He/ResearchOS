from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass(frozen=True)
class BenchmarkScenarioResult:
    scenario_id: str
    task_kind: str
    success: bool
    latency_ms: int
    provider_route: str
    retrieval_used: bool
    tool_calls: tuple[str, ...] = ()
    checkpoint_used: bool = False
    score_breakdown: dict[str, float] = field(default_factory=dict)
    failure_reason: str = ""


@dataclass(frozen=True)
class BenchmarkRunSummary:
    benchmark_id: str
    project_id: str | None
    success_rate: float
    routing_accuracy: float
    retrieval_usefulness: float
    resume_success: float
    branch_selection_quality: float
    scenario_count: int
    scenarios: tuple[BenchmarkScenarioResult, ...] = ()
    failure_reasons: tuple[str, ...] = ()
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
