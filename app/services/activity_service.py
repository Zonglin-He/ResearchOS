from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.db.sqlite import SQLiteDatabase
from app.schemas.activity import ConversationMessage, RunEvent
from app.services.registry_store import append_jsonl, ensure_parent, read_jsonl


class ActivityService:
    def __init__(
        self,
        *,
        database: SQLiteDatabase | None = None,
        events_path: str | Path = "state/run_events.jsonl",
        conversations_path: str | Path = "state/conversation_messages.jsonl",
    ) -> None:
        self.database = database
        self.events_path = Path(events_path).expanduser().resolve()
        self.conversations_path = Path(conversations_path).expanduser().resolve()

    @staticmethod
    def discussion_thread_id(*, human_select_task_id: str, gap_id: str) -> str:
        return f"discussion:{human_select_task_id}:{gap_id}"

    def record_event(self, event: RunEvent) -> RunEvent:
        if self.database is not None:
            with self.database.connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO run_events (
                        project_id,
                        task_id,
                        run_id,
                        event_type,
                        message,
                        payload_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.project_id,
                        event.task_id,
                        event.run_id,
                        event.event_type,
                        event.message,
                        json.dumps(event.payload, ensure_ascii=False),
                        event.created_at.isoformat(),
                    ),
                )
                event.event_id = int(cursor.lastrowid)
            return event

        payload = {
            "event_id": event.event_id or self._next_jsonl_event_id(),
            "project_id": event.project_id,
            "task_id": event.task_id,
            "run_id": event.run_id,
            "event_type": event.event_type,
            "message": event.message,
            "payload": event.payload,
            "created_at": event.created_at.isoformat(),
        }
        append_jsonl(self.events_path, payload)
        event.event_id = int(payload["event_id"])
        return event

    def list_events(self, project_id: str, *, after_id: int = 0, limit: int = 100) -> list[RunEvent]:
        if self.database is not None:
            with self.database.connect() as connection:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM run_events
                    WHERE project_id = ? AND event_id > ?
                    ORDER BY event_id
                    LIMIT ?
                    """,
                    (project_id, after_id, limit),
                ).fetchall()
            return [self._row_to_event(row) for row in rows]

        rows = [
            row
            for row in read_jsonl(self.events_path)
            if row.get("project_id") == project_id and int(row.get("event_id", 0)) > after_id
        ]
        rows.sort(key=lambda row: int(row.get("event_id", 0)))
        return [self._json_to_event(row) for row in rows[:limit]]

    def record_conversation_message(self, message: ConversationMessage) -> ConversationMessage:
        if self.database is not None:
            with self.database.connect() as connection:
                cursor = connection.execute(
                    """
                    INSERT INTO conversation_messages (
                        project_id,
                        thread_id,
                        human_select_task_id,
                        gap_id,
                        role,
                        content,
                        metadata_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        message.project_id,
                        message.thread_id,
                        message.human_select_task_id,
                        message.gap_id,
                        message.role,
                        message.content,
                        json.dumps(message.metadata, ensure_ascii=False),
                        message.created_at.isoformat(),
                    ),
                )
                message.message_id = int(cursor.lastrowid)
            return message

        payload = {
            "message_id": message.message_id or self._next_jsonl_message_id(),
            "project_id": message.project_id,
            "thread_id": message.thread_id,
            "human_select_task_id": message.human_select_task_id,
            "gap_id": message.gap_id,
            "role": message.role,
            "content": message.content,
            "metadata": message.metadata,
            "created_at": message.created_at.isoformat(),
        }
        append_jsonl(self.conversations_path, payload)
        message.message_id = int(payload["message_id"])
        return message

    def list_conversation_messages(
        self,
        *,
        project_id: str,
        thread_id: str,
        limit: int = 200,
    ) -> list[ConversationMessage]:
        if self.database is not None:
            with self.database.connect() as connection:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM conversation_messages
                    WHERE project_id = ? AND thread_id = ?
                    ORDER BY message_id
                    LIMIT ?
                    """,
                    (project_id, thread_id, limit),
                ).fetchall()
            return [self._row_to_message(row) for row in rows]

        rows = [
            row
            for row in read_jsonl(self.conversations_path)
            if row.get("project_id") == project_id and row.get("thread_id") == thread_id
        ]
        rows.sort(key=lambda row: int(row.get("message_id", 0)))
        return [self._json_to_message(row) for row in rows[:limit]]

    def latest_event_id(self, project_id: str) -> int:
        if self.database is not None:
            with self.database.connect() as connection:
                row = connection.execute(
                    "SELECT COALESCE(MAX(event_id), 0) AS max_id FROM run_events WHERE project_id = ?",
                    (project_id,),
                ).fetchone()
            return int(row["max_id"] if row is not None else 0)

        max_id = 0
        for row in read_jsonl(self.events_path):
            if row.get("project_id") != project_id:
                continue
            max_id = max(max_id, int(row.get("event_id", 0)))
        return max_id

    def latest_task_event_times(
        self,
        project_id: str,
        *,
        task_ids: list[str],
    ) -> dict[str, datetime]:
        normalized_ids = [task_id for task_id in task_ids if task_id]
        if not normalized_ids:
            return {}

        if self.database is not None:
            placeholders = ", ".join("?" for _ in normalized_ids)
            with self.database.connect() as connection:
                rows = connection.execute(
                    f"""
                    SELECT task_id, MAX(created_at) AS last_created_at
                    FROM run_events
                    WHERE project_id = ? AND task_id IN ({placeholders})
                    GROUP BY task_id
                    """,
                    (project_id, *normalized_ids),
                ).fetchall()
            return {
                str(row["task_id"]): datetime.fromisoformat(row["last_created_at"])
                for row in rows
                if row["task_id"] and row["last_created_at"]
            }

        latest: dict[str, datetime] = {}
        allowed = set(normalized_ids)
        for row in read_jsonl(self.events_path):
            if row.get("project_id") != project_id:
                continue
            task_id = str(row.get("task_id") or "")
            if task_id not in allowed:
                continue
            created_at = datetime.fromisoformat(str(row.get("created_at")))
            previous = latest.get(task_id)
            if previous is None or created_at > previous:
                latest[task_id] = created_at
        return latest

    def _next_jsonl_event_id(self) -> int:
        ensure_parent(self.events_path)
        rows = read_jsonl(self.events_path)
        return max((int(row.get("event_id", 0)) for row in rows), default=0) + 1

    def _next_jsonl_message_id(self) -> int:
        ensure_parent(self.conversations_path)
        rows = read_jsonl(self.conversations_path)
        return max((int(row.get("message_id", 0)) for row in rows), default=0) + 1

    @staticmethod
    def _row_to_event(row: object) -> RunEvent:
        return RunEvent(
            event_id=row["event_id"],
            project_id=row["project_id"],
            task_id=row["task_id"],
            run_id=row["run_id"],
            event_type=row["event_type"],
            message=row["message"],
            payload=json.loads(row["payload_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _json_to_event(row: dict[str, object]) -> RunEvent:
        return RunEvent(
            event_id=int(row.get("event_id", 0)),
            project_id=str(row.get("project_id", "")),
            task_id=str(row.get("task_id")) if row.get("task_id") else None,
            run_id=str(row.get("run_id")) if row.get("run_id") else None,
            event_type=str(row.get("event_type", "")),
            message=str(row.get("message", "")),
            payload=row.get("payload", {}) if isinstance(row.get("payload"), dict) else {},
            created_at=datetime.fromisoformat(str(row.get("created_at"))),
        )

    @staticmethod
    def _row_to_message(row: object) -> ConversationMessage:
        return ConversationMessage(
            message_id=row["message_id"],
            project_id=row["project_id"],
            thread_id=row["thread_id"],
            human_select_task_id=row["human_select_task_id"],
            gap_id=row["gap_id"],
            role=row["role"],
            content=row["content"],
            metadata=json.loads(row["metadata_json"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _json_to_message(row: dict[str, object]) -> ConversationMessage:
        return ConversationMessage(
            message_id=int(row.get("message_id", 0)),
            project_id=str(row.get("project_id", "")),
            thread_id=str(row.get("thread_id", "")),
            human_select_task_id=str(row.get("human_select_task_id"))
            if row.get("human_select_task_id")
            else None,
            gap_id=str(row.get("gap_id")) if row.get("gap_id") else None,
            role=str(row.get("role", "")),
            content=str(row.get("content", "")),
            metadata=row.get("metadata", {}) if isinstance(row.get("metadata"), dict) else {},
            created_at=datetime.fromisoformat(str(row.get("created_at"))),
        )
