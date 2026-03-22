from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from app.db.sqlite import SQLiteDatabase
from app.schemas.approval import Approval
from app.services.registry_store import append_jsonl, read_jsonl, to_record


class ApprovalService:
    def __init__(
        self,
        registry_path: str | Path = "registry/approvals.jsonl",
        *,
        database: SQLiteDatabase | None = None,
    ) -> None:
        self.registry_path = Path(registry_path).expanduser().resolve()
        self.database = database

    def record_approval(self, approval: Approval) -> Approval:
        append_jsonl(self.registry_path, to_record(approval))
        if self.database is not None:
            with self.database.connect() as connection:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO approvals (
                        approval_id,
                        project_id,
                        target_type,
                        target_id,
                        decision,
                        approved_by,
                        created_at,
                        record_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        approval.approval_id,
                        approval.project_id,
                        approval.target_type,
                        approval.target_id,
                        approval.decision,
                        approval.approved_by,
                        approval.created_at.isoformat(),
                        json.dumps(to_record(approval), ensure_ascii=False),
                    ),
                )
        return approval

    def list_approvals(self) -> list[Approval]:
        if self.database is not None:
            self._hydrate_database_if_needed()
            with self.database.connect() as connection:
                rows = connection.execute(
                    "SELECT record_json FROM approvals ORDER BY created_at, approval_id"
                ).fetchall()
            return [self._row_to_approval(json.loads(row["record_json"])) for row in rows]
        rows = read_jsonl(self.registry_path)
        return [self._row_to_approval(row) for row in rows]

    def _hydrate_database_if_needed(self) -> None:
        if self.database is None:
            return
        with self.database.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM approvals").fetchone()
            count = int(row["count"] if row is not None else 0)
        if count > 0:
            return
        rows = read_jsonl(self.registry_path)
        if not rows:
            return
        with self.database.connect() as connection:
            for row in rows:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO approvals (
                        approval_id,
                        project_id,
                        target_type,
                        target_id,
                        decision,
                        approved_by,
                        created_at,
                        record_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        row["approval_id"],
                        row["project_id"],
                        row["target_type"],
                        row["target_id"],
                        row["decision"],
                        row["approved_by"],
                        row["created_at"],
                        json.dumps(row, ensure_ascii=False),
                    ),
                )

    @staticmethod
    def _row_to_approval(row: dict[str, object]) -> Approval:
        return [
            Approval(
                approval_id=row["approval_id"],
                project_id=row["project_id"],
                target_type=row["target_type"],
                target_id=row["target_id"],
                approved_by=row["approved_by"],
                decision=row["decision"],
                comment=row.get("comment", ""),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        ][0]

    def list_pending(self) -> list[Approval]:
        return [approval for approval in self.list_approvals() if approval.decision == "pending"]
