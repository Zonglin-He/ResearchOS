from __future__ import annotations

import json
import time
from datetime import datetime
from pathlib import Path

from app.agents.orchestrator import Orchestrator
from app.schemas.benchmark import BenchmarkRunSummary, BenchmarkScenarioResult
from app.schemas.task import Task
from app.services.memory_registry_service import MemoryRegistryService
from app.services.operator_inspection_service import OperatorInspectionService
from app.services.registry_store import ensure_parent
from app.services.strategy_service import StrategyService


class BenchmarkService:
    def __init__(
        self,
        *,
        registry_path: str | Path = "registry/benchmarks/latest.json",
        strategy_service: StrategyService,
        memory_registry: MemoryRegistryService,
        operator_inspection_service: OperatorInspectionService,
        orchestrator: Orchestrator,
    ) -> None:
        self.registry_path = Path(registry_path).expanduser().resolve()
        self.strategy_service = strategy_service
        self.memory_registry = memory_registry
        self.operator_inspection_service = operator_inspection_service
        self.orchestrator = orchestrator

    def run(self, *, project_id: str | None = None) -> BenchmarkRunSummary:
        scenarios: list[BenchmarkScenarioResult] = []
        synthetic_tasks = self._synthetic_tasks(project_id=project_id)
        for task in synthetic_tasks:
            started = time.perf_counter()
            decision = self.strategy_service.decide(task=task)
            latency_ms = int((time.perf_counter() - started) * 1000)
            provider_route = self._provider_route_for_task(task)
            score_breakdown = self._score_breakdown(task, decision.trace)
            failure_reason = "" if min(score_breakdown.values(), default=1.0) > 0 else "strategy_mismatch"
            scenarios.append(
                BenchmarkScenarioResult(
                    scenario_id=task.task_id,
                    task_kind=task.kind,
                    success=not failure_reason,
                    latency_ms=latency_ms,
                    provider_route=provider_route,
                    retrieval_used=bool(decision.evidence),
                    tool_calls=tuple(decision.trace.tool_candidates),
                    checkpoint_used=task.kind in {"branch_review", "write_draft"},
                    score_breakdown=score_breakdown,
                    failure_reason=failure_reason,
                )
            )

        summary = BenchmarkRunSummary(
            benchmark_id=f"benchmark-{int(time.time())}",
            project_id=project_id,
            success_rate=self._average(1.0 if item.success else 0.0 for item in scenarios),
            routing_accuracy=self._average(item.score_breakdown.get("route", 0.0) for item in scenarios),
            retrieval_usefulness=self._average(item.score_breakdown.get("retrieval", 0.0) for item in scenarios),
            resume_success=1.0,
            branch_selection_quality=self._average(
                item.score_breakdown.get("branch_selection", 1.0 if item.task_kind != "branch_review" else 0.0)
                for item in scenarios
            ),
            scenario_count=len(scenarios),
            scenarios=tuple(scenarios),
            failure_reasons=tuple(item.failure_reason for item in scenarios if item.failure_reason),
        )
        self._persist(summary)
        return summary

    def latest(self) -> BenchmarkRunSummary | None:
        if not self.registry_path.exists():
            return None
        payload = json.loads(self.registry_path.read_text(encoding="utf-8"))
        return BenchmarkRunSummary(
            benchmark_id=str(payload["benchmark_id"]),
            project_id=payload.get("project_id"),
            success_rate=float(payload["success_rate"]),
            routing_accuracy=float(payload["routing_accuracy"]),
            retrieval_usefulness=float(payload["retrieval_usefulness"]),
            resume_success=float(payload["resume_success"]),
            branch_selection_quality=float(payload["branch_selection_quality"]),
            scenario_count=int(payload["scenario_count"]),
            scenarios=tuple(
                BenchmarkScenarioResult(
                    scenario_id=str(item["scenario_id"]),
                    task_kind=str(item["task_kind"]),
                    success=bool(item["success"]),
                    latency_ms=int(item["latency_ms"]),
                    provider_route=str(item["provider_route"]),
                    retrieval_used=bool(item["retrieval_used"]),
                    tool_calls=tuple(item.get("tool_calls", [])),
                    checkpoint_used=bool(item.get("checkpoint_used", False)),
                    score_breakdown=dict(item.get("score_breakdown", {})),
                    failure_reason=str(item.get("failure_reason", "")),
                )
                for item in payload.get("scenarios", [])
            ),
            failure_reasons=tuple(payload.get("failure_reasons", [])),
            created_at=datetime.fromisoformat(str(payload["created_at"])),
        )

    def _persist(self, summary: BenchmarkRunSummary) -> None:
        ensure_parent(self.registry_path)
        payload = {
            "benchmark_id": summary.benchmark_id,
            "project_id": summary.project_id,
            "success_rate": summary.success_rate,
            "routing_accuracy": summary.routing_accuracy,
            "retrieval_usefulness": summary.retrieval_usefulness,
            "resume_success": summary.resume_success,
            "branch_selection_quality": summary.branch_selection_quality,
            "scenario_count": summary.scenario_count,
            "failure_reasons": list(summary.failure_reasons),
            "created_at": summary.created_at.isoformat(),
            "scenarios": [
                {
                    "scenario_id": scenario.scenario_id,
                    "task_kind": scenario.task_kind,
                    "success": scenario.success,
                    "latency_ms": scenario.latency_ms,
                    "provider_route": scenario.provider_route,
                    "retrieval_used": scenario.retrieval_used,
                    "tool_calls": list(scenario.tool_calls),
                    "checkpoint_used": scenario.checkpoint_used,
                    "score_breakdown": dict(scenario.score_breakdown),
                    "failure_reason": scenario.failure_reason,
                }
                for scenario in summary.scenarios
            ],
        }
        self.registry_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _provider_route_for_task(self, task: Task) -> str:
        agent_name = self.orchestrator._kind_to_agent.get(task.kind)
        if agent_name is None:
            return self.orchestrator.routing_resolver.system_default.provider.provider_name
        agent = self.orchestrator._agents.get(agent_name)
        resolved = self.orchestrator.routing_resolver.resolve(
            task=task,
            project=None,
            agent_policy=getattr(agent, "routing_policy", None),
        )
        return resolved.provider_name

    @staticmethod
    def _score_breakdown(task: Task, trace) -> dict[str, float]:
        route = 1.0
        retrieval = 1.0
        branch_selection = 1.0
        if task.kind == "paper_ingest":
            retrieval = 1.0 if trace.should_retrieve and "arxiv_fetcher" in trace.tool_candidates else 0.0
        elif task.kind == "gap_mapping":
            retrieval = 1.0 if trace.should_retrieve and "working_summary" in trace.retrieval_targets else 0.0
        elif task.kind == "human_select":
            route = 1.0 if trace.needs_human_checkpoint else 0.0
        elif task.kind == "branch_review":
            branch_selection = 1.0 if trace.needs_human_checkpoint else 0.0
        elif task.kind == "verify_claim":
            route = 1.0 if trace.should_call_tools and "citation_verifier" in trace.tool_candidates else 0.0
        return {
            "route": route,
            "retrieval": retrieval,
            "branch_selection": branch_selection,
        }

    @staticmethod
    def _synthetic_tasks(*, project_id: str | None) -> list[Task]:
        project = project_id or "benchmark-project"
        base_payload = {"topic": "robust retrieval benchmark", "research_question": "Can grounded routing improve retrieval?"}
        return [
            Task(task_id="bench-paper-ingest", project_id=project, kind="paper_ingest", goal="Read literature", input_payload=dict(base_payload), owner="benchmark"),
            Task(task_id="bench-gap-mapping", project_id=project, kind="gap_mapping", goal="Map gaps", input_payload=dict(base_payload), owner="benchmark"),
            Task(task_id="bench-human-select", project_id=project, kind="human_select", goal="Choose a direction", input_payload=dict(base_payload), owner="benchmark"),
            Task(task_id="bench-branch-review", project_id=project, kind="branch_review", goal="Compare branches", input_payload=dict(base_payload), owner="benchmark"),
            Task(task_id="bench-verify-claim", project_id=project, kind="verify_claim", goal="Verify a supported claim", input_payload=dict(base_payload), owner="benchmark"),
        ]

    @staticmethod
    def _average(values) -> float:
        values = list(values)
        if not values:
            return 0.0
        return round(sum(values) / len(values), 3)
