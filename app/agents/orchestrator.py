from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.agents.base import BaseAgent
from app.core.error_summary import summarize_error_detail
from app.routing.models import ResolvedDispatch
from app.routing.resolver import RoutingResolver
from app.schemas.artifact import ArtifactRecord
from app.schemas.activity import RunEvent
from app.schemas.context import RunContext
from app.schemas.result import AgentResult
from app.schemas.strategy import HandoffPacket, RetrievalEvidence, StrategyTrace
from app.schemas.task import Task, TaskStatus
from app.services.activity_service import ActivityService
from app.services.approval_service import ApprovalService
from app.services.artifact_service import ArtifactService
from app.services.checkpoint_service import CheckpointService
from app.services.gap_map_service import GapMapService
from app.services.memory_registry_service import MemoryRegistryService
from app.services.project_service import ProjectService
from app.services.strategy_service import StrategyService
from app.services.task_service import TaskService
from app.services.lessons_service import LessonsService
from app.services.registry_store import to_record
from app.workflows.research_flow import FlowEvent, stage_for_task_kind


@dataclass
class OrchestratorDispatch:
    task: Task
    result: AgentResult


class Orchestrator:
    def __init__(
        self,
        task_service: TaskService,
        project_service: ProjectService | None = None,
        routing_resolver: RoutingResolver | None = None,
        lessons_service: LessonsService | None = None,
        approval_service: ApprovalService | None = None,
        gap_map_service: GapMapService | None = None,
        strategy_service: StrategyService | None = None,
        artifact_service: ArtifactService | None = None,
        memory_registry_service: MemoryRegistryService | None = None,
        artifacts_dir: str | Path = "artifacts",
        activity_service: ActivityService | None = None,
        checkpoint_service: CheckpointService | None = None,
    ) -> None:
        self.task_service = task_service
        self.project_service = project_service
        self.routing_resolver = routing_resolver
        self.lessons_service = lessons_service
        self.approval_service = approval_service
        self.gap_map_service = gap_map_service
        self.strategy_service = strategy_service
        self.artifact_service = artifact_service
        self.memory_registry_service = memory_registry_service
        self.artifacts_dir = Path(artifacts_dir)
        self.activity_service = activity_service
        self.checkpoint_service = checkpoint_service
        self._agents: dict[str, BaseAgent] = {}
        self._kind_to_agent: dict[str, str] = {}

    def register_agent(self, agent: BaseAgent, *, handles: set[str] | None = None) -> None:
        self._agents[agent.name] = agent
        for kind in handles or set():
            self._kind_to_agent[kind] = agent.name

    def preview_routing(self, task_id: str) -> ResolvedDispatch | None:
        task = self.task_service.get_task(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        agent_name = task.assigned_agent or self._kind_to_agent.get(task.kind)
        if agent_name is None:
            return task.last_run_routing
        agent = self._agents.get(agent_name)
        if agent is None:
            raise KeyError(f"Agent not found: {agent_name}")
        return self._resolve_routing(task, agent)

    async def dispatch(self, task_id: str) -> OrchestratorDispatch:
        task = self.task_service.get_task(task_id)
        if task is None:
            raise KeyError(f"Task not found: {task_id}")
        if not self.task_service.dependencies_satisfied(task):
            dependency_ids = []
            for dependency_id in task.depends_on:
                dependency = self.task_service.get_task(dependency_id)
                if dependency is None or dependency.status != TaskStatus.SUCCEEDED:
                    dependency_ids.append(dependency_id)
            self._record_event(
                task.project_id,
                event_type="task.dependency_blocked",
                message=f"Task {task.task_id} is blocked by unsatisfied dependencies",
                task_id=task.task_id,
                payload={"depends_on": dependency_ids},
            )
            raise ValueError(f"Task dependencies are not satisfied: {dependency_ids}")
        if task.next_retry_at is not None and not self.task_service.is_runnable(task):
            raise ValueError(
                f"Task retry is scheduled for {task.next_retry_at.isoformat()}; it is not runnable yet"
            )

        agent_name = task.assigned_agent or self._kind_to_agent.get(task.kind)
        if agent_name is None:
            raise ValueError(f"No agent registered for task kind: {task.kind}")

        agent = self._agents.get(agent_name)
        if agent is None:
            raise KeyError(f"Agent not found: {agent_name}")

        routing = self._resolve_routing(task, agent)
        strategy_trace, retrieval_evidence = self._resolve_strategy(task, project_id=task.project_id)
        task.latest_strategy_trace = strategy_trace
        task.latest_retrieval_evidence = list(retrieval_evidence)
        if routing is not None:
            routing.strategy_metadata = {
                "should_retrieve": strategy_trace.should_retrieve,
                "retrieval_targets": list(strategy_trace.retrieval_targets),
                "should_call_tools": strategy_trace.should_call_tools,
                "tool_candidates": list(strategy_trace.tool_candidates),
                "needs_human_checkpoint": strategy_trace.needs_human_checkpoint,
            }
        if task.status != TaskStatus.RUNNING:
            task = self.task_service.update_status(task.task_id, TaskStatus.RUNNING)
        task.assigned_agent = agent_name
        task.last_run_routing = routing
        task.next_retry_at = None
        task = self.task_service.save_task(task)
        self._record_strategy_events(task, strategy_trace, retrieval_evidence)
        strategy_artifact_ids = self._register_strategy_artifacts(
            run_id=f"run-{task.task_id}",
            strategy_trace=strategy_trace,
            retrieval_evidence=retrieval_evidence,
        )
        if self.project_service is not None:
            stage = stage_for_task_kind(task.kind)
            self.project_service.transition_flow(
                task.project_id,
                event=FlowEvent.START,
                stage=stage,
                task_id=task.task_id,
                note=f"dispatch started for {task.kind}",
            )

        checkpoint_path = self._save_checkpoint(
            task,
            stage="dispatch_started",
            payload={"routing": self._routing_record(routing), "agent_name": agent_name},
        )
        context = RunContext(
            run_id=f"run-{task.task_id}",
            project_id=task.project_id,
            task_id=task.task_id,
            artifacts_dir=str(self.artifacts_dir),
            max_steps=routing.max_steps if routing is not None and routing.max_steps is not None else 12,
            routing=routing,
            prior_lessons=self._resolve_prior_lessons(task, agent_name, routing),
            checkpoint_dir=str(self.checkpoint_service.root_dir) if self.checkpoint_service is not None else "",
            checkpoint_path=checkpoint_path,
            resume_from_checkpoint=self._load_checkpoint(task.task_id),
            strategy_trace=strategy_trace,
            retrieval_evidence_ids=[*strategy_artifact_ids, *[item.source_id for item in retrieval_evidence]],
            checkpoint_recorder=lambda stage, payload: self._save_checkpoint(task, stage=stage, payload=payload),
        )
        if task.latest_handoff_packet is not None:
            self._record_event(
                task.project_id,
                event_type="handoff.accepted",
                message=f"Handoff accepted for task {task.task_id}",
                task_id=task.task_id,
                run_id=context.run_id,
                payload=to_record(task.latest_handoff_packet),
            )
        self._record_event(
            task.project_id,
            event_type="task.dispatched",
            message=f"Dispatch started for task {task.task_id}",
            task_id=task.task_id,
            run_id=context.run_id,
            payload={"agent_name": agent_name, "routing": self._routing_record(routing)},
        )
        try:
            result = await agent.run(task, context)
        except Exception as error:
            error_detail = summarize_error_detail(str(error), max_length=360)
            task = self.task_service.mark_task_failed(
                task.task_id,
                error_detail=error_detail,
                retryable=True,
            )
            task.checkpoint_path = self._save_checkpoint(
                task,
                stage="dispatch_failed",
                payload={"error": error_detail, "agent_name": agent_name},
            )
            task = self.task_service.save_task(task)
            if self.project_service is not None:
                self.project_service.transition_flow(
                    task.project_id,
                    event=FlowEvent.FAIL,
                    stage=stage_for_task_kind(task.kind),
                    task_id=task.task_id,
                    note=error_detail,
                )
            result = AgentResult(
                status="fail",
                output={"error": error_detail},
                audit_notes=[f"dispatch failed: {error_detail}"],
                evidence_used=[item.source_id for item in retrieval_evidence],
            )
            return OrchestratorDispatch(task=task, result=result)

        if context.routing is not None:
            result.routing = context.routing
            task.last_run_routing = context.routing
            task = self.task_service.save_task(task)
            result.audit_notes.append(self._routing_audit_note(context.routing))
        if not result.evidence_used:
            result.evidence_used = [item.source_id for item in retrieval_evidence]
        if self.lessons_service is not None:
            self.lessons_service.capture_agent_outcome(
                task=task,
                agent_name=agent_name,
                result=result,
            )
        self._record_memory(task=task, result=result, agent_name=agent_name)
        self._apply_gap_debate_side_effects(task, result)

        final_status = self._result_to_status(result.status)
        task = self._create_next_tasks(task, result.next_tasks, result=result, from_agent=agent_name)
        task = self.task_service.save_task(task)
        if final_status is not None:
            task = self.task_service.update_status(task.task_id, final_status)
        self._sync_project_stage(task, result)
        task.checkpoint_path = self._save_checkpoint(
            task,
            stage=f"dispatch_{result.status}",
            payload={
                "artifacts": list(result.artifacts),
                "output": result.output,
                "next_tasks": [next_task.task_id for next_task in result.next_tasks],
                "audit_notes": list(result.audit_notes),
                "strategy_trace": to_record(strategy_trace),
                "retrieval_evidence": to_record(retrieval_evidence),
                "handoff_packet": to_record(result.handoff_packet),
            },
        )
        task = self.task_service.save_task(task)
        self._record_event(
            task.project_id,
            event_type="task.completed",
            message=f"Dispatch finished for task {task.task_id} with status {task.status.value}",
            task_id=task.task_id,
            run_id=context.run_id,
            payload={
                "status": task.status.value,
                "artifacts": list(result.artifacts),
                "next_tasks": [next_task.task_id for next_task in result.next_tasks],
            },
        )

        return OrchestratorDispatch(task=task, result=result)

    def _resolve_routing(self, task: Task, agent: BaseAgent) -> ResolvedDispatch | None:
        if self.routing_resolver is None:
            return task.last_run_routing
        project = None
        if self.project_service is not None:
            project = self.project_service.get_project(task.project_id)
        return self.routing_resolver.resolve(
            task=task,
            project=project,
            agent_policy=getattr(agent, "routing_policy", None),
        )

    def _resolve_prior_lessons(
        self,
        task: Task,
        agent_name: str,
        routing: ResolvedDispatch | None,
    ):
        if self.lessons_service is None:
            return []
        return self.lessons_service.get_relevant_lessons(
            task_kind=task.kind,
            agent_name=agent_name,
            provider_name=routing.provider_name if routing is not None else None,
            model_name=routing.model if routing is not None else None,
            repository_ref=task.input_payload.get("repository"),
            dataset_ref=task.input_payload.get("dataset_snapshot")
            or task.input_payload.get("dataset"),
            topic=task.input_payload.get("topic"),
        )

    def _resolve_strategy(
        self,
        task: Task,
        *,
        project_id: str,
    ) -> tuple[StrategyTrace, tuple[RetrievalEvidence, ...]]:
        if self.strategy_service is None:
            return (
                StrategyTrace(
                    task_id=task.task_id,
                    project_id=project_id,
                    should_retrieve=False,
                    reasoning_summary="strategy service unavailable",
                ),
                tuple(),
            )
        project = None if self.project_service is None else self.project_service.get_project(project_id)
        decision = self.strategy_service.decide(task=task, project=project)
        return decision.trace, decision.evidence

    def _create_next_tasks(
        self,
        task: Task,
        next_tasks: list[Task],
        *,
        result: AgentResult,
        from_agent: str,
    ) -> Task:
        project_narrative = self._build_project_narrative(task.project_id)
        approval_constraints = self._approval_constraints(task)
        created_handoffs: list[HandoffPacket] = []
        for next_task in next_tasks:
            if task.task_id not in next_task.depends_on:
                next_task.depends_on = [*next_task.depends_on, task.task_id]
            if next_task.parent_task_id is None:
                next_task.parent_task_id = task.task_id
            next_task.input_payload.setdefault("project_narrative", project_narrative)
            next_task.input_payload.setdefault("upstream_task_kind", task.kind)
            next_task.input_payload.setdefault("upstream_summary", task.goal.strip() or task.kind)
            if approval_constraints:
                raw_existing = next_task.input_payload.get("human_constraints", [])
                existing = [
                    str(item).strip()
                    for item in (raw_existing if isinstance(raw_existing, list) else [])
                    if str(item).strip()
                ]
                for item in approval_constraints:
                    if item not in existing:
                        existing.append(item)
                next_task.input_payload["human_constraints"] = existing
            handoff_packet = self._handoff_for_next_task(
                current_task=task,
                next_task=next_task,
                result=result,
                from_agent=from_agent,
            )
            next_task.latest_handoff_packet = handoff_packet
            next_task.input_payload["handoff_packet"] = to_record(handoff_packet)
            self.task_service.create_task(next_task)
            created_handoffs.append(handoff_packet)
            self._record_event(
                task.project_id,
                event_type="handoff.created",
                message=f"Handoff created from {task.task_id} to {next_task.task_id}",
                task_id=task.task_id,
                payload=to_record(handoff_packet),
            )
            self._register_handoff_artifact(
                run_id=f"run-{task.task_id}",
                next_task=next_task,
                packet=handoff_packet,
            )
        if created_handoffs:
            task.latest_handoff_packet = created_handoffs[0]
        return task

    def _build_project_narrative(self, project_id: str) -> str:
        tasks = [
            task
            for task in self.task_service.list_tasks()
            if task.project_id == project_id and task.status == TaskStatus.SUCCEEDED
        ]
        key_kinds = {"paper_ingest", "gap_mapping", "human_select", "hypothesis_draft", "build_spec", "implement_experiment", "analyze_run"}
        lines: list[str] = []
        for task in sorted(tasks, key=lambda item: item.created_at):
            if task.kind not in key_kinds:
                continue
            summary = task.goal.strip()
            if not summary:
                summary = task.kind
            lines.append(f"{task.kind}: {summary}")
        return " | ".join(lines[-6:])

    def _approval_constraints(self, task: Task) -> list[str]:
        if self.approval_service is None:
            return []
        candidates = [
            self.approval_service.latest_target_approval(
                project_id=task.project_id,
                target_type=task.kind,
                target_id=task.task_id,
            ),
            self.approval_service.latest_target_approval(
                project_id=task.project_id,
                target_type="task",
                target_id=task.task_id,
            ),
        ]
        constraints: list[str] = []
        for approval in candidates:
            if approval is None or approval.decision != "approved_with_conditions":
                continue
            text = approval.condition_text.strip()
            if text and text not in constraints:
                constraints.append(text)
        return constraints

    def _apply_gap_debate_side_effects(self, task: Task, result: AgentResult) -> None:
        if task.kind != "gap_debate":
            return
        candidate_debates = result.output.get("candidate_debates", [])
        if not isinstance(candidate_debates, list) or not candidate_debates:
            return
        topic = str(task.input_payload.get("topic", "")).strip()
        if topic and self.gap_map_service is not None:
            self.gap_map_service.attach_debate_weaknesses(topic, candidate_debates)
        parent_id = task.parent_task_id
        if not parent_id:
            return
        for sibling in self.task_service.list_tasks():
            if sibling.project_id != task.project_id or sibling.kind != "human_select":
                continue
            if sibling.parent_task_id != parent_id:
                continue
            ranked_candidates = sibling.input_payload.get("ranked_candidates", [])
            if not isinstance(ranked_candidates, list):
                continue
            updated = False
            for candidate in ranked_candidates:
                if not isinstance(candidate, dict):
                    continue
                gap_id = str(candidate.get("gap_id", "")).strip()
                matches = [
                    item
                    for item in candidate_debates
                    if isinstance(item, dict) and str(item.get("gap_id", "")).strip() == gap_id
                ]
                if not matches:
                    continue
                weaknesses = [
                    str(item.get("weakness", "")).strip()
                    for item in matches
                    if str(item.get("weakness", "")).strip()
                ]
                constraints = [
                    str(value).strip()
                    for item in matches
                    for value in item.get("recommended_constraints", [])
                    if str(value).strip()
                ]
                candidate["debate_weaknesses"] = list(dict.fromkeys(weaknesses))
                candidate["recommended_constraints"] = list(dict.fromkeys(constraints))
                updated = True
            if updated:
                sibling.input_payload["ranked_candidates"] = ranked_candidates
                self.task_service.save_task(sibling)

    def _save_checkpoint(self, task: Task, *, stage: str, payload: dict[str, object]) -> str | None:
        if self.checkpoint_service is None:
            return None
        checkpoint_path = self.checkpoint_service.save(task=task, stage=stage, payload=payload)
        self._record_event(
            task.project_id,
            event_type="checkpoint.saved",
            message=f"Checkpoint saved for {task.task_id}: {stage}",
            task_id=task.task_id,
            payload={"stage": stage, "checkpoint_path": checkpoint_path},
        )
        return checkpoint_path

    def _load_checkpoint(self, task_id: str) -> dict[str, object] | None:
        if self.checkpoint_service is None:
            return None
        return self.checkpoint_service.load(task_id)

    def _sync_project_stage(self, task: Task, result: AgentResult) -> None:
        if self.project_service is None:
            return
        next_task_kinds = [next_task.kind for next_task in result.next_tasks]
        stage = stage_for_task_kind(
            task.kind,
            terminal_status=task.status,
            next_task_kinds=next_task_kinds,
        )
        if stage is None:
            return
        if task.status == TaskStatus.SUCCEEDED:
            self.project_service.transition_flow(
                task.project_id,
                event=FlowEvent.SUCCEED,
                stage=stage,
                task_id=task.task_id,
                note=f"{task.kind} completed",
            )
            return
        if task.status == TaskStatus.WAITING_APPROVAL:
            self.project_service.transition_flow(
                task.project_id,
                event=FlowEvent.REQUIRE_APPROVAL,
                stage=stage,
                task_id=task.task_id,
                note=f"{task.kind} requires approval",
            )
            return
        if task.status == TaskStatus.FAILED:
            self.project_service.transition_flow(
                task.project_id,
                event=FlowEvent.FAIL,
                stage=stage,
                task_id=task.task_id,
                note=task.last_error or f"{task.kind} failed",
            )
            return
        if task.status == TaskStatus.BLOCKED:
            self.project_service.transition_flow(
                task.project_id,
                event=FlowEvent.PAUSE,
                stage=stage,
                task_id=task.task_id,
                note=f"{task.kind} handed off for manual follow-up",
            )
            return
        self.project_service.update_stage(task.project_id, stage)

    def _record_event(
        self,
        project_id: str,
        *,
        event_type: str,
        message: str,
        task_id: str | None = None,
        run_id: str | None = None,
        payload: dict[str, object] | None = None,
    ) -> None:
        if self.activity_service is None:
            return
        self.activity_service.record_event(
            RunEvent(
                project_id=project_id,
                task_id=task_id,
                run_id=run_id,
                event_type=event_type,
                message=message,
                payload=dict(payload or {}),
            )
        )

    def _record_strategy_events(
        self,
        task: Task,
        strategy_trace: StrategyTrace,
        retrieval_evidence: tuple[RetrievalEvidence, ...],
    ) -> None:
        self._record_event(
            task.project_id,
            event_type="strategy.decided",
            message=f"Strategy resolved for task {task.task_id}",
            task_id=task.task_id,
            payload=to_record(strategy_trace),
        )
        if retrieval_evidence:
            self._record_event(
                task.project_id,
                event_type="retrieval.started",
                message=f"Retrieval started for task {task.task_id}",
                task_id=task.task_id,
                payload={"targets": list(strategy_trace.retrieval_targets)},
            )
            self._record_event(
                task.project_id,
                event_type="retrieval.completed",
                message=f"Retrieval completed for task {task.task_id}",
                task_id=task.task_id,
                payload={"evidence_count": len(retrieval_evidence)},
            )

    def _register_strategy_artifacts(
        self,
        *,
        run_id: str,
        strategy_trace: StrategyTrace,
        retrieval_evidence: tuple[RetrievalEvidence, ...],
    ) -> list[str]:
        if self.artifact_service is None:
            return []
        strategy_artifact = ArtifactRecord(
            artifact_id=f"{run_id}-strategy-trace",
            run_id=run_id,
            kind="strategy_trace",
            path="",
            hash="",
            metadata=to_record(strategy_trace),
        )
        self.artifact_service.register_artifact(strategy_artifact)
        artifact_ids = [strategy_artifact.artifact_id]
        if retrieval_evidence:
            retrieval_artifact = ArtifactRecord(
                artifact_id=f"{run_id}-retrieval-bundle",
                run_id=run_id,
                kind="retrieval_bundle",
                path="",
                hash="",
                metadata={"evidence": to_record(retrieval_evidence)},
            )
            self.artifact_service.register_artifact(retrieval_artifact)
            artifact_ids.append(retrieval_artifact.artifact_id)
        return artifact_ids

    def _register_handoff_artifact(
        self,
        *,
        run_id: str,
        next_task: Task,
        packet: HandoffPacket,
    ) -> None:
        if self.artifact_service is None:
            return
        self.artifact_service.register_artifact(
            ArtifactRecord(
                artifact_id=f"{run_id}-handoff-{next_task.task_id}",
                run_id=run_id,
                kind="handoff_packet",
                path="",
                hash="",
                metadata=to_record(packet),
            )
        )

    def _handoff_for_next_task(
        self,
        *,
        current_task: Task,
        next_task: Task,
        result: AgentResult,
        from_agent: str,
    ) -> HandoffPacket:
        if result.handoff_packet is not None:
            return result.handoff_packet
        evidence_ids = list(dict.fromkeys([*result.artifacts, *result.evidence_used]))
        return HandoffPacket(
            from_agent=self._collaboration_role(from_agent, current_task.kind),
            to_agent=self._collaboration_role(
                next_task.assigned_agent or self._kind_to_agent.get(next_task.kind, ""),
                next_task.kind,
            ),
            task_kind=next_task.kind,
            objective=next_task.goal,
            required_inputs=tuple(
                field
                for field in (
                    "project_narrative",
                    "upstream_summary",
                    "research_question",
                    "topic",
                    "branch_id",
                )
                if field in next_task.input_payload
            ),
            attached_evidence_ids=tuple(evidence_ids),
            blocking_questions=tuple(
                str(item)
                for item in result.output.get("blocking_issues", [])
                if str(item).strip()
            ),
            done_definition=f"Complete task {next_task.kind} and persist artifacts, audit notes, and any follow-up tasks.",
        )

    def _record_memory(self, *, task: Task, result: AgentResult, agent_name: str) -> None:
        if self.memory_registry_service is None:
            return
        summary = str(result.output.get("summary", "")).strip() or (
            result.audit_notes[0] if result.audit_notes else task.goal
        )
        bucket = self._memory_bucket_for(task.kind, result.status)
        tags = [
            task.kind,
            agent_name,
            str(task.input_payload.get("topic", "")).strip(),
            str(task.input_payload.get("branch_id", "")).strip(),
        ]
        self.memory_registry_service.record_task_summary(
            project_id=task.project_id,
            task_id=task.task_id,
            bucket=bucket,
            summary=summary,
            confidence=0.8 if result.status == "success" else 0.6,
            tags=[tag for tag in tags if tag],
            metadata={
                "title": task.goal,
                "status": result.status,
                "task_kind": task.kind,
                "artifact_ids": list(result.artifacts),
            },
        )

    @staticmethod
    def _memory_bucket_for(task_kind: str, result_status: str) -> str:
        if task_kind in {"paper_ingest", "repo_ingest", "read_source", "gap_mapping", "map_gaps"}:
            return "retrieval_note"
        if task_kind in {"human_select", "branch_review", "build_spec"}:
            return "research_decision"
        if result_status == "success":
            return "working_summary"
        return "execution_lesson"

    @staticmethod
    def _collaboration_role(agent_name: str, task_kind: str) -> str:
        normalized = f"{agent_name} {task_kind}".lower()
        if "branch_manager" in normalized or "hypothesis" in normalized or "branch_review" in normalized:
            return "Planner"
        if "reader" in normalized or "mapper" in normalized or "gap" in normalized:
            return "Retriever/Mapper"
        if "builder" in normalized or "analyst" in normalized or "experiment" in normalized or "run" in normalized:
            return "Executor/Analyzer"
        return "Reviewer/Writer"

    @staticmethod
    def _routing_record(routing: ResolvedDispatch | None) -> dict[str, object] | None:
        if routing is None:
            return None
        return {
            "provider_name": routing.provider_name,
            "model": routing.model,
            "role_name": routing.role_name,
            "capability_class": routing.capability_class,
            "max_steps": routing.max_steps,
            "strategy_metadata": dict(routing.strategy_metadata),
        }

    @staticmethod
    def _routing_audit_note(routing: ResolvedDispatch) -> str:
        return (
            "dispatch routing resolved "
            f"role={routing.role_name or '<unknown>'} "
            f"capability={routing.capability_class or '<unknown>'} "
            f"provider={routing.provider_name} "
            f"model={routing.model or '<default>'} "
            f"decision_reason={routing.decision_reason or '<none>'} "
            f"fallback_reason={routing.fallback_reason or '<none>'} "
            f"sources={routing.sources}"
        )

    @staticmethod
    def _result_to_status(result_status: str) -> TaskStatus | None:
        if result_status == "success":
            return TaskStatus.SUCCEEDED
        if result_status == "fail":
            return TaskStatus.FAILED
        if result_status == "needs_approval":
            return TaskStatus.WAITING_APPROVAL
        if result_status == "handoff":
            return TaskStatus.BLOCKED
        return None
