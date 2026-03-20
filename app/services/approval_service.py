from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.schemas.approval import Approval
from app.services.registry_store import append_jsonl, read_jsonl, to_record


class ApprovalService:
    def __init__(self, registry_path: str | Path = "registry/approvals.jsonl") -> None:
        self.registry_path = Path(registry_path).expanduser().resolve()

    def record_approval(self, approval: Approval) -> Approval:
        append_jsonl(self.registry_path, to_record(approval))
        return approval

    def list_approvals(self) -> list[Approval]:
        rows = read_jsonl(self.registry_path)
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
            for row in rows
        ]

    def list_pending(self) -> list[Approval]:
        return [approval for approval in self.list_approvals() if approval.decision == "pending"]
