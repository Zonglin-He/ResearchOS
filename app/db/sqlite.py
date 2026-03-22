from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    stage TEXT NOT NULL DEFAULT 'NEW_TOPIC',
    dispatch_profile_json TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    kind TEXT NOT NULL,
    goal TEXT NOT NULL,
    input_payload_json TEXT NOT NULL,
    owner TEXT NOT NULL,
    assigned_agent TEXT,
    status TEXT NOT NULL,
    parent_task_id TEXT,
    depends_on_json TEXT,
    join_key TEXT,
    fanout_group TEXT,
    experiment_proposal_id TEXT,
    dispatch_profile_json TEXT,
    last_run_routing_json TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 2,
    last_error TEXT,
    next_retry_at TEXT,
    checkpoint_path TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(project_id)
);

CREATE TABLE IF NOT EXISTS run_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    task_id TEXT,
    run_id TEXT,
    event_type TEXT NOT NULL,
    message TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_run_events_project_event_id
ON run_events(project_id, event_id);

CREATE TABLE IF NOT EXISTS conversation_messages (
    message_id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    thread_id TEXT NOT NULL,
    human_select_task_id TEXT,
    gap_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_conversation_messages_project_thread
ON conversation_messages(project_id, thread_id, message_id);

CREATE TABLE IF NOT EXISTS paper_cards (
    paper_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    task_type TEXT NOT NULL,
    record_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_paper_cards_title
ON paper_cards(title);

CREATE TABLE IF NOT EXISTS gap_maps (
    topic TEXT PRIMARY KEY,
    record_json TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lessons (
    lesson_id TEXT PRIMARY KEY,
    lesson_kind TEXT NOT NULL,
    task_kind TEXT,
    agent_name TEXT,
    provider_name TEXT,
    model_name TEXT,
    source_task_id TEXT,
    created_at TEXT NOT NULL,
    record_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_lessons_task_kind_created_at
ON lessons(task_kind, created_at);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id TEXT NOT NULL,
    decision TEXT NOT NULL,
    approved_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    record_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_approvals_project_decision
ON approvals(project_id, decision, created_at);
"""


class SQLiteDatabase:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)
            self._ensure_column(connection, "projects", "dispatch_profile_json", "TEXT")
            self._ensure_column(connection, "projects", "stage", "TEXT NOT NULL DEFAULT 'NEW_TOPIC'")
            self._ensure_column(connection, "tasks", "dispatch_profile_json", "TEXT")
            self._ensure_column(connection, "tasks", "last_run_routing_json", "TEXT")
            self._ensure_column(connection, "tasks", "experiment_proposal_id", "TEXT")
            self._ensure_column(connection, "tasks", "depends_on_json", "TEXT")
            self._ensure_column(connection, "tasks", "join_key", "TEXT")
            self._ensure_column(connection, "tasks", "fanout_group", "TEXT")
            self._ensure_column(connection, "tasks", "retry_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(connection, "tasks", "max_retries", "INTEGER NOT NULL DEFAULT 2")
            self._ensure_column(connection, "tasks", "last_error", "TEXT")
            self._ensure_column(connection, "tasks", "next_retry_at", "TEXT")
            self._ensure_column(connection, "tasks", "checkpoint_path", "TEXT")

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @staticmethod
    def _ensure_column(
        connection: sqlite3.Connection,
        table_name: str,
        column_name: str,
        column_type: str,
    ) -> None:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        existing = {row["name"] for row in rows}
        if column_name in existing:
            return
        connection.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}")
