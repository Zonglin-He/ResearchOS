import sqlite3
from pathlib import Path

from app.db.session import create_session_factory


def test_create_session_factory_backfills_new_task_columns_for_existing_tables(tmp_path: Path) -> None:
    database_path = tmp_path / "legacy.db"
    with sqlite3.connect(database_path) as connection:
        connection.executescript(
            """
            CREATE TABLE projects (
                project_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                status TEXT NOT NULL,
                stage TEXT NOT NULL,
                dispatch_profile JSON,
                created_at TEXT NOT NULL
            );
            CREATE TABLE tasks (
                task_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                goal TEXT NOT NULL,
                input_payload JSON NOT NULL,
                owner TEXT NOT NULL,
                assigned_agent TEXT,
                status TEXT NOT NULL,
                parent_task_id TEXT,
                depends_on JSON,
                join_key TEXT,
                fanout_group TEXT,
                experiment_proposal_id TEXT,
                dispatch_profile JSON,
                last_run_routing JSON,
                retry_count INTEGER NOT NULL,
                max_retries INTEGER NOT NULL,
                last_error TEXT,
                next_retry_at TEXT,
                checkpoint_path TEXT,
                created_at TEXT NOT NULL
            );
            """
        )

    create_session_factory(f"sqlite:///{database_path}")

    with sqlite3.connect(database_path) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(tasks)").fetchall()
        }

    assert "latest_strategy_trace" in columns
    assert "latest_retrieval_evidence" in columns
    assert "latest_handoff_packet" in columns
