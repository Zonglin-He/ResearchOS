from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum

from app.core.enums import Stage
from app.schemas.task import TaskStatus


class FlowStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    BLOCKED_APPROVAL = "blocked_approval"
    PAUSED = "paused"
    RETRYING = "retrying"
    FAILED = "failed"
    DONE = "done"


class FlowEvent(str, Enum):
    CREATE = "create"
    SYNC_STAGE = "sync_stage"
    START = "start"
    SUCCEED = "succeed"
    REQUIRE_APPROVAL = "require_approval"
    APPROVE = "approve"
    REJECT = "reject"
    FAIL = "fail"
    RETRY = "retry"
    RESUME = "resume"
    PAUSE = "pause"
    PIVOT = "pivot"
    REFINE = "refine"


_NEXT_STAGE: dict[Stage, Stage | None] = {
    Stage.NEW_TOPIC: Stage.INGEST_PAPERS,
    Stage.INGEST_PAPERS: Stage.MAP_GAPS,
    Stage.BUILD_PAPER_CARDS: Stage.MAP_GAPS,
    Stage.MAP_GAPS: Stage.HUMAN_SELECT,
    Stage.HUMAN_SELECT: Stage.FREEZE_TOPIC,
    Stage.FREEZE_TOPIC: Stage.FREEZE_SPEC,
    Stage.FREEZE_SPEC: Stage.REPRO_BASELINES,
    Stage.REPRO_BASELINES: Stage.IMPLEMENT_IDEA,
    Stage.IMPLEMENT_IDEA: Stage.RUN_EXPERIMENTS,
    Stage.RUN_EXPERIMENTS: Stage.AUDIT_RESULTS,
    Stage.AUDIT_RESULTS: Stage.FREEZE_RESULTS,
    Stage.FREEZE_RESULTS: Stage.WRITE_DRAFT,
    Stage.WRITE_DRAFT: Stage.REVIEW_DRAFT,
    Stage.REVIEW_DRAFT: Stage.STYLE_PASS,
    Stage.STYLE_PASS: Stage.SUBMISSION_READY,
    Stage.SUBMISSION_READY: None,
}

_GATE_ROLLBACK: dict[Stage, Stage] = {
    Stage.HUMAN_SELECT: Stage.MAP_GAPS,
    Stage.FREEZE_SPEC: Stage.FREEZE_TOPIC,
    Stage.AUDIT_RESULTS: Stage.RUN_EXPERIMENTS,
    Stage.WRITE_DRAFT: Stage.FREEZE_RESULTS,
}

_PIVOT_TARGET: dict[Stage, Stage] = {
    Stage.IMPLEMENT_IDEA: Stage.MAP_GAPS,
    Stage.RUN_EXPERIMENTS: Stage.MAP_GAPS,
    Stage.AUDIT_RESULTS: Stage.MAP_GAPS,
    Stage.FREEZE_RESULTS: Stage.MAP_GAPS,
    Stage.WRITE_DRAFT: Stage.HUMAN_SELECT,
    Stage.REVIEW_DRAFT: Stage.HUMAN_SELECT,
    Stage.STYLE_PASS: Stage.HUMAN_SELECT,
}

_REFINE_TARGET: dict[Stage, Stage] = {
    Stage.FREEZE_SPEC: Stage.IMPLEMENT_IDEA,
    Stage.REPRO_BASELINES: Stage.REPRO_BASELINES,
    Stage.IMPLEMENT_IDEA: Stage.IMPLEMENT_IDEA,
    Stage.RUN_EXPERIMENTS: Stage.RUN_EXPERIMENTS,
    Stage.AUDIT_RESULTS: Stage.RUN_EXPERIMENTS,
    Stage.FREEZE_RESULTS: Stage.RUN_EXPERIMENTS,
    Stage.WRITE_DRAFT: Stage.WRITE_DRAFT,
    Stage.REVIEW_DRAFT: Stage.WRITE_DRAFT,
    Stage.STYLE_PASS: Stage.REVIEW_DRAFT,
}

_DEFAULT_GATE_STAGES = frozenset(
    {
        Stage.HUMAN_SELECT,
        Stage.FREEZE_SPEC,
        Stage.AUDIT_RESULTS,
        Stage.WRITE_DRAFT,
    }
)

_TASK_STAGE_MAP: dict[str, Stage] = {
    "paper_ingest": Stage.INGEST_PAPERS,
    "repo_ingest": Stage.INGEST_PAPERS,
    "read_source": Stage.INGEST_PAPERS,
    "gap_mapping": Stage.MAP_GAPS,
    "map_gaps": Stage.MAP_GAPS,
    "gap_debate": Stage.MAP_GAPS,
    "human_select": Stage.HUMAN_SELECT,
    "hypothesis_draft": Stage.FREEZE_TOPIC,
    "build_spec": Stage.FREEZE_SPEC,
    "reproduce_baseline": Stage.REPRO_BASELINES,
    "branch_plan": Stage.IMPLEMENT_IDEA,
    "implement_experiment": Stage.RUN_EXPERIMENTS,
    "run_experiment": Stage.RUN_EXPERIMENTS,
    "branch_review": Stage.AUDIT_RESULTS,
    "analyze_run": Stage.AUDIT_RESULTS,
    "analyze_results": Stage.AUDIT_RESULTS,
    "review_build": Stage.FREEZE_RESULTS,
    "audit_run": Stage.FREEZE_RESULTS,
    "verify_evidence": Stage.FREEZE_RESULTS,
    "verify_claim": Stage.FREEZE_RESULTS,
    "verify_results": Stage.FREEZE_RESULTS,
    "write_draft": Stage.WRITE_DRAFT,
    "write_section": Stage.WRITE_DRAFT,
    "style_pass": Stage.STYLE_PASS,
    "polish_draft": Stage.STYLE_PASS,
    "archive_research": Stage.SUBMISSION_READY,
    "archive_run": Stage.SUBMISSION_READY,
    "record_lessons": Stage.SUBMISSION_READY,
}


@dataclass(frozen=True)
class FlowTransitionRecord:
    stage: Stage
    event: FlowEvent
    status: FlowStatus
    decision: str
    note: str = ""
    task_id: str | None = None
    rollback_stage: Stage | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass(frozen=True)
class ResearchFlowSnapshot:
    stage: Stage = Stage.NEW_TOPIC
    status: FlowStatus = FlowStatus.PENDING
    decision: str = "proceed"
    checkpoint_required: bool = False
    active_task_id: str | None = None
    rollback_stage: Stage | None = None
    note: str = ""
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    history: tuple[FlowTransitionRecord, ...] = ()

    def to_metadata(self) -> dict[str, object]:
        return {
            "stage": self.stage.value,
            "status": self.status.value,
            "decision": self.decision,
            "checkpoint_required": self.checkpoint_required,
            "active_task_id": self.active_task_id,
            "rollback_stage": self.rollback_stage.value if self.rollback_stage is not None else None,
            "note": self.note,
            "updated_at": self.updated_at.isoformat(),
            "history": [
                {
                    "stage": item.stage.value,
                    "event": item.event.value,
                    "status": item.status.value,
                    "decision": item.decision,
                    "note": item.note,
                    "task_id": item.task_id,
                    "rollback_stage": item.rollback_stage.value if item.rollback_stage is not None else None,
                    "created_at": item.created_at.isoformat(),
                }
                for item in self.history
            ],
        }

    @classmethod
    def from_metadata(cls, payload: dict[str, object] | None, *, fallback_stage: Stage = Stage.NEW_TOPIC) -> ResearchFlowSnapshot:
        if not isinstance(payload, dict):
            return cls(stage=fallback_stage)
        history: list[FlowTransitionRecord] = []
        for item in payload.get("history", []):
            if not isinstance(item, dict):
                continue
            try:
                history.append(
                    FlowTransitionRecord(
                        stage=Stage(str(item.get("stage", fallback_stage.value))),
                        event=FlowEvent(str(item.get("event", FlowEvent.CREATE.value))),
                        status=FlowStatus(str(item.get("status", FlowStatus.PENDING.value))),
                        decision=str(item.get("decision", "proceed")),
                        note=str(item.get("note", "")),
                        task_id=str(item.get("task_id")) if item.get("task_id") else None,
                        rollback_stage=(
                            Stage(str(item.get("rollback_stage")))
                            if item.get("rollback_stage")
                            else None
                        ),
                        created_at=datetime.fromisoformat(str(item.get("created_at"))),
                    )
                )
            except (ValueError, TypeError):
                continue
        try:
            updated_at = datetime.fromisoformat(str(payload.get("updated_at")))
        except (ValueError, TypeError):
            updated_at = datetime.now(timezone.utc)
        stage_value = str(payload.get("stage", fallback_stage.value))
        try:
            stage = Stage(stage_value)
        except ValueError:
            stage = fallback_stage
        status_value = str(payload.get("status", FlowStatus.PENDING.value))
        try:
            status = FlowStatus(status_value)
        except ValueError:
            status = FlowStatus.PENDING
        rollback_raw = payload.get("rollback_stage")
        rollback_stage = None
        if rollback_raw:
            try:
                rollback_stage = Stage(str(rollback_raw))
            except ValueError:
                rollback_stage = None
        return cls(
            stage=stage,
            status=status,
            decision=str(payload.get("decision", "proceed")),
            checkpoint_required=bool(payload.get("checkpoint_required", False)),
            active_task_id=str(payload.get("active_task_id")) if payload.get("active_task_id") else None,
            rollback_stage=rollback_stage,
            note=str(payload.get("note", "")),
            updated_at=updated_at,
            history=tuple(history),
        )


def next_stage_for(stage: Stage) -> Stage | None:
    return _NEXT_STAGE.get(stage)


def rollback_stage_for(stage: Stage) -> Stage:
    return _GATE_ROLLBACK.get(stage, stage)


def pivot_target_for(stage: Stage) -> Stage:
    return _PIVOT_TARGET.get(stage, rollback_stage_for(stage))


def refine_target_for(stage: Stage) -> Stage:
    return _REFINE_TARGET.get(stage, stage)


def default_gate_stages() -> frozenset[Stage]:
    return _DEFAULT_GATE_STAGES


def stage_for_task_kind(
    task_kind: str,
    *,
    terminal_status: TaskStatus | None = None,
    next_task_kinds: list[str] | None = None,
) -> Stage | None:
    _ = terminal_status
    _ = next_task_kinds
    return _TASK_STAGE_MAP.get(task_kind)


def available_flow_actions(snapshot: ResearchFlowSnapshot) -> tuple[str, ...]:
    if snapshot.status == FlowStatus.PENDING:
        return ("start", "pause")
    if snapshot.status == FlowStatus.RUNNING:
        return ("pause", "refine", "pivot")
    if snapshot.status == FlowStatus.BLOCKED_APPROVAL:
        return ("approve", "reject", "pause")
    if snapshot.status == FlowStatus.FAILED:
        return ("retry", "refine", "pivot")
    if snapshot.status == FlowStatus.RETRYING:
        return ("resume", "pause")
    if snapshot.status == FlowStatus.PAUSED:
        return ("resume", "retry")
    return ()


def transition_flow(
    snapshot: ResearchFlowSnapshot | None,
    *,
    event: FlowEvent,
    stage: Stage | None = None,
    task_id: str | None = None,
    note: str = "",
) -> ResearchFlowSnapshot:
    current = snapshot or ResearchFlowSnapshot(stage=stage or Stage.NEW_TOPIC)
    current_stage = stage or current.stage
    now = datetime.now(timezone.utc)
    decision = current.decision
    checkpoint_required = current.checkpoint_required
    rollback_stage = current.rollback_stage
    active_task_id = task_id if task_id is not None else current.active_task_id
    status = current.status
    next_stage = current_stage

    if event == FlowEvent.CREATE:
        next_stage = current_stage
        status = FlowStatus.PENDING
        decision = "create"
        checkpoint_required = False
        rollback_stage = rollback_stage_for(current_stage)
    elif event == FlowEvent.SYNC_STAGE:
        next_stage = current_stage
        status = current.status if current.status != FlowStatus.DONE else FlowStatus.PENDING
        decision = "sync"
        checkpoint_required = current.checkpoint_required
        rollback_stage = rollback_stage_for(current_stage)
    elif event == FlowEvent.START:
        next_stage = current_stage
        status = FlowStatus.RUNNING
        decision = "start"
        checkpoint_required = False
        rollback_stage = rollback_stage_for(current_stage)
        active_task_id = task_id
    elif event == FlowEvent.SUCCEED:
        candidate = next_stage_for(current_stage)
        next_stage = candidate or current_stage
        status = FlowStatus.PENDING if candidate is not None else FlowStatus.DONE
        decision = "proceed"
        checkpoint_required = True
        rollback_stage = rollback_stage_for(next_stage)
        active_task_id = None
    elif event == FlowEvent.REQUIRE_APPROVAL:
        next_stage = current_stage
        status = FlowStatus.BLOCKED_APPROVAL
        decision = "block"
        checkpoint_required = True
        rollback_stage = rollback_stage_for(current_stage)
        active_task_id = task_id
    elif event == FlowEvent.APPROVE:
        candidate = next_stage_for(current_stage)
        next_stage = candidate or current_stage
        status = FlowStatus.PENDING if candidate is not None else FlowStatus.DONE
        decision = "approve"
        checkpoint_required = True
        rollback_stage = rollback_stage_for(next_stage)
        active_task_id = None
    elif event == FlowEvent.REJECT:
        next_stage = rollback_stage_for(current_stage)
        status = FlowStatus.PENDING
        decision = "reject"
        checkpoint_required = True
        rollback_stage = next_stage
        active_task_id = None
    elif event == FlowEvent.FAIL:
        next_stage = current_stage
        status = FlowStatus.FAILED
        decision = "fail"
        checkpoint_required = True
        rollback_stage = rollback_stage_for(current_stage)
    elif event == FlowEvent.RETRY:
        next_stage = current_stage
        status = FlowStatus.RETRYING
        decision = "retry"
        checkpoint_required = False
    elif event == FlowEvent.RESUME:
        next_stage = current_stage
        status = FlowStatus.RUNNING
        decision = "resume"
        checkpoint_required = False
        active_task_id = task_id
    elif event == FlowEvent.PAUSE:
        next_stage = current_stage
        status = FlowStatus.PAUSED
        decision = "pause"
        checkpoint_required = True
    elif event == FlowEvent.PIVOT:
        next_stage = pivot_target_for(current_stage)
        status = FlowStatus.PENDING
        decision = "pivot"
        checkpoint_required = True
        rollback_stage = next_stage
        active_task_id = None
    elif event == FlowEvent.REFINE:
        next_stage = refine_target_for(current_stage)
        status = FlowStatus.PENDING
        decision = "refine"
        checkpoint_required = True
        rollback_stage = rollback_stage_for(next_stage)
        active_task_id = None

    history = list(current.history)
    history.append(
        FlowTransitionRecord(
            stage=current_stage,
            event=event,
            status=status,
            decision=decision,
            note=note,
            task_id=task_id,
            rollback_stage=rollback_stage,
            created_at=now,
        )
    )
    return ResearchFlowSnapshot(
        stage=next_stage,
        status=status,
        decision=decision,
        checkpoint_required=checkpoint_required,
        active_task_id=active_task_id,
        rollback_stage=rollback_stage,
        note=note,
        updated_at=now,
        history=tuple(history[-32:]),
    )


@dataclass
class ResearchFlow:
    snapshot: ResearchFlowSnapshot = field(default_factory=ResearchFlowSnapshot)

    def advance(self, next_stage: Stage) -> Stage:
        self.snapshot = ResearchFlowSnapshot(
            stage=next_stage,
            status=FlowStatus.PENDING,
            decision="advance",
            rollback_stage=rollback_stage_for(next_stage),
        )
        return self.snapshot.stage
