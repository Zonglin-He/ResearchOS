from __future__ import annotations

import json
from datetime import datetime

from app.db.repositories.task_repository import TaskRepository
from app.db.sqlite import SQLiteDatabase
from app.routing import dispatch_profile_from_dict, resolved_dispatch_from_dict
from app.schemas.task import Task, TaskStatus
from app.schemas.strategy import HandoffPacket, RetrievalEvidence, StrategyTrace
from app.services.registry_store import to_record


class SQLiteTaskRepository(TaskRepository):
    def __init__(self, database: SQLiteDatabase) -> None:
        self.database = database

    def create(self, task: Task) -> Task:
        with self.database.connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO tasks (
                    task_id,
                    project_id,
                    kind,
                    goal,
                    input_payload_json,
                    owner,
                    assigned_agent,
                    status,
                    parent_task_id,
                    depends_on_json,
                    join_key,
                    fanout_group,
                    experiment_proposal_id,
                    dispatch_profile_json,
                    last_run_routing_json,
                    retry_count,
                    max_retries,
                    last_error,
                    next_retry_at,
                    checkpoint_path,
                    latest_strategy_trace_json,
                    latest_retrieval_evidence_json,
                    latest_handoff_packet_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.task_id,
                    task.project_id,
                    task.kind,
                    task.goal,
                    json.dumps(task.input_payload),
                    task.owner,
                    task.assigned_agent,
                    task.status.value,
                    task.parent_task_id,
                    json.dumps(task.depends_on),
                    task.join_key,
                    task.fanout_group,
                    task.experiment_proposal_id,
                    json.dumps(to_record(task.dispatch_profile))
                    if task.dispatch_profile is not None
                    else None,
                    json.dumps(to_record(task.last_run_routing))
                    if task.last_run_routing is not None
                    else None,
                    task.retry_count,
                    task.max_retries,
                    task.last_error,
                    task.next_retry_at.isoformat() if task.next_retry_at is not None else None,
                    task.checkpoint_path,
                    json.dumps(to_record(task.latest_strategy_trace))
                    if task.latest_strategy_trace is not None
                    else None,
                    json.dumps(to_record(task.latest_retrieval_evidence)),
                    json.dumps(to_record(task.latest_handoff_packet))
                    if task.latest_handoff_packet is not None
                    else None,
                    task.created_at.isoformat(),
                ),
            )
        return task

    def update(self, task: Task) -> Task:
        with self.database.connect() as connection:
            connection.execute(
                """
                UPDATE tasks
                SET project_id = ?,
                    kind = ?,
                    goal = ?,
                    input_payload_json = ?,
                    owner = ?,
                    assigned_agent = ?,
                    status = ?,
                    parent_task_id = ?,
                    depends_on_json = ?,
                    join_key = ?,
                    fanout_group = ?,
                    experiment_proposal_id = ?,
                    dispatch_profile_json = ?,
                    last_run_routing_json = ?,
                    retry_count = ?,
                    max_retries = ?,
                    last_error = ?,
                    next_retry_at = ?,
                    checkpoint_path = ?,
                    latest_strategy_trace_json = ?,
                    latest_retrieval_evidence_json = ?,
                    latest_handoff_packet_json = ?,
                    created_at = ?
                WHERE task_id = ?
                """,
                (
                    task.project_id,
                    task.kind,
                    task.goal,
                    json.dumps(task.input_payload),
                    task.owner,
                    task.assigned_agent,
                    task.status.value,
                    task.parent_task_id,
                    json.dumps(task.depends_on),
                    task.join_key,
                    task.fanout_group,
                    task.experiment_proposal_id,
                    json.dumps(to_record(task.dispatch_profile))
                    if task.dispatch_profile is not None
                    else None,
                    json.dumps(to_record(task.last_run_routing))
                    if task.last_run_routing is not None
                    else None,
                    task.retry_count,
                    task.max_retries,
                    task.last_error,
                    task.next_retry_at.isoformat() if task.next_retry_at is not None else None,
                    task.checkpoint_path,
                    json.dumps(to_record(task.latest_strategy_trace))
                    if task.latest_strategy_trace is not None
                    else None,
                    json.dumps(to_record(task.latest_retrieval_evidence)),
                    json.dumps(to_record(task.latest_handoff_packet))
                    if task.latest_handoff_packet is not None
                    else None,
                    task.created_at.isoformat(),
                    task.task_id,
                ),
            )
        return task

    def get_by_id(self, task_id: str) -> Task | None:
        with self.database.connect() as connection:
            row = connection.execute(
                "SELECT * FROM tasks WHERE task_id = ?",
                (task_id,),
            ).fetchone()
        if row is None:
            return None
        return self._row_to_task(row)

    def list_all(self) -> list[Task]:
        with self.database.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM tasks ORDER BY created_at, task_id"
            ).fetchall()
        return [self._row_to_task(row) for row in rows]

    def delete(self, task_id: str) -> None:
        with self.database.connect() as connection:
            connection.execute("DELETE FROM tasks WHERE task_id = ?", (task_id,))

    @staticmethod
    def _row_to_task(row: object) -> Task:
        strategy_payload = (
            json.loads(row["latest_strategy_trace_json"])
            if row["latest_strategy_trace_json"]
            else None
        )
        handoff_payload = (
            json.loads(row["latest_handoff_packet_json"])
            if row["latest_handoff_packet_json"]
            else None
        )
        return Task(
            task_id=row["task_id"],
            project_id=row["project_id"],
            kind=row["kind"],
            goal=row["goal"],
            input_payload=json.loads(row["input_payload_json"]),
            owner=row["owner"],
            assigned_agent=row["assigned_agent"],
            status=TaskStatus(row["status"]),
            parent_task_id=row["parent_task_id"],
            depends_on=json.loads(row["depends_on_json"]) if row["depends_on_json"] else [],
            join_key=row["join_key"],
            fanout_group=row["fanout_group"],
            experiment_proposal_id=row["experiment_proposal_id"],
            dispatch_profile=dispatch_profile_from_dict(
                json.loads(row["dispatch_profile_json"])
                if row["dispatch_profile_json"]
                else None
            ),
            last_run_routing=resolved_dispatch_from_dict(
                json.loads(row["last_run_routing_json"])
                if row["last_run_routing_json"]
                else None
            ),
            retry_count=row["retry_count"] or 0,
            max_retries=row["max_retries"] or 2,
            last_error=row["last_error"],
            next_retry_at=datetime.fromisoformat(row["next_retry_at"])
            if row["next_retry_at"]
            else None,
            checkpoint_path=row["checkpoint_path"],
            latest_strategy_trace=StrategyTrace(
                task_id=str(strategy_payload["task_id"]),
                project_id=str(strategy_payload["project_id"]),
                should_retrieve=bool(strategy_payload["should_retrieve"]),
                retrieval_targets=tuple(strategy_payload.get("retrieval_targets", [])),
                should_call_tools=bool(strategy_payload.get("should_call_tools", False)),
                tool_candidates=tuple(strategy_payload.get("tool_candidates", [])),
                needs_human_checkpoint=bool(strategy_payload.get("needs_human_checkpoint", False)),
                reasoning_summary=str(strategy_payload.get("reasoning_summary", "")),
                created_at=datetime.fromisoformat(str(strategy_payload["created_at"])),
            ) if strategy_payload else None,
            latest_retrieval_evidence=[
                RetrievalEvidence(**item)
                for item in json.loads(row["latest_retrieval_evidence_json"])
            ] if row["latest_retrieval_evidence_json"] else [],
            latest_handoff_packet=HandoffPacket(
                from_agent=str(handoff_payload["from_agent"]),
                to_agent=str(handoff_payload["to_agent"]),
                task_kind=str(handoff_payload["task_kind"]),
                objective=str(handoff_payload["objective"]),
                required_inputs=tuple(handoff_payload.get("required_inputs", [])),
                attached_evidence_ids=tuple(handoff_payload.get("attached_evidence_ids", [])),
                blocking_questions=tuple(handoff_payload.get("blocking_questions", [])),
                done_definition=str(handoff_payload.get("done_definition", "")),
            ) if handoff_payload else None,
            created_at=datetime.fromisoformat(row["created_at"]),
        )
