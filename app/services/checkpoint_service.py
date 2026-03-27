from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.schemas.task import Task
from app.services.registry_store import ensure_parent


class CheckpointService:
    def __init__(self, root_dir: str | Path = "artifacts/checkpoints") -> None:
        self.root_dir = Path(root_dir).expanduser().resolve()

    def checkpoint_path(self, task_id: str) -> Path:
        return self.root_dir / f"{self._safe_task_filename(task_id)}.json"

    def save(
        self,
        *,
        task: Task,
        stage: str,
        payload: dict[str, Any],
    ) -> str:
        path = self.checkpoint_path(task.task_id)
        ensure_parent(path)
        record = {
            "task_id": task.task_id,
            "project_id": task.project_id,
            "stage": stage,
            "payload": payload,
            "saved_at": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
        return str(path)

    def load(self, task_id: str) -> dict[str, Any] | None:
        path = self.checkpoint_path(task_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _safe_task_filename(task_id: str) -> str:
        max_length = 48
        raw = str(task_id).strip() or "task"
        sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "-", raw)
        sanitized = re.sub(r"\s+", "-", sanitized).strip(".- ") or "task"
        if sanitized == raw and len(sanitized) <= max_length:
            return sanitized
        digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]
        prefix_length = max(8, max_length - len(digest) - 1)
        trimmed = sanitized[:prefix_length].rstrip(".- ") or "task"
        return f"{trimmed}-{digest}"
