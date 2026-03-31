from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BenchmarkRunRequest(BaseModel):
    project_id: str | None = None


class BenchmarkScenarioResultRead(BaseModel):
    scenario_id: str
    task_kind: str
    success: bool
    latency_ms: int
    provider_route: str
    retrieval_used: bool
    tool_calls: list[str] = Field(default_factory=list)
    checkpoint_used: bool = False
    score_breakdown: dict[str, float] = Field(default_factory=dict)
    failure_reason: str = ""


class BenchmarkRunSummaryRead(BaseModel):
    benchmark_id: str
    project_id: str | None = None
    success_rate: float
    routing_accuracy: float
    retrieval_usefulness: float
    resume_success: float
    branch_selection_quality: float
    scenario_count: int
    scenarios: list[BenchmarkScenarioResultRead] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)
    created_at: datetime
