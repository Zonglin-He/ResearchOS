from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS projects (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
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
    experiment_proposal_id TEXT,
    dispatch_profile_json TEXT,
    last_run_routing_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(project_id) REFERENCES projects(project_id)
);
"""


class SQLiteDatabase:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)

    def initialize(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as connection:
            connection.executescript(SCHEMA_SQL)
            self._ensure_column(connection, "projects", "dispatch_profile_json", "TEXT")
            self._ensure_column(connection, "tasks", "dispatch_profile_json", "TEXT")
            self._ensure_column(connection, "tasks", "last_run_routing_json", "TEXT")
            self._ensure_column(connection, "tasks", "experiment_proposal_id", "TEXT")

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
