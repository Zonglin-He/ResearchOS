from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.schemas.memory import MemoryRecord
from app.services.registry_store import append_jsonl, read_jsonl


class MemoryRegistryService:
    def __init__(self, registry_path: str | Path = "registry/memory.jsonl") -> None:
        self.registry_path = Path(registry_path).expanduser().resolve()

    def record(self, record: MemoryRecord) -> MemoryRecord:
        append_jsonl(
            self.registry_path,
            {
                "record_id": record.record_id,
                "project_id": record.project_id,
                "bucket": record.bucket,
                "source_task_id": record.source_task_id,
                "summary": record.summary,
                "confidence": record.confidence,
                "created_at": record.created_at.isoformat(),
                "expires_at": record.expires_at.isoformat() if record.expires_at else None,
                "tags": list(record.tags),
                "metadata": dict(record.metadata),
            },
        )
        return record

    def record_task_summary(
        self,
        *,
        project_id: str,
        task_id: str,
        bucket: str,
        summary: str,
        confidence: float = 0.7,
        tags: list[str] | tuple[str, ...] = (),
        metadata: dict[str, object] | None = None,
        ttl_days: int = 30,
    ) -> MemoryRecord:
        normalized_summary = summary.strip()
        return self.record(
            MemoryRecord(
                record_id=f"memory:{project_id}:{task_id}:{bucket}:{len(self.list_records(project_id=project_id)) + 1}",
                project_id=project_id,
                bucket=bucket,
                source_task_id=task_id,
                summary=normalized_summary,
                confidence=max(0.0, min(1.0, confidence)),
                expires_at=datetime.now(timezone.utc) + timedelta(days=max(1, ttl_days)),
                tags=tuple(dict.fromkeys(tag.strip() for tag in tags if str(tag).strip())),
                metadata=dict(metadata or {}),
            )
        )

    def list_records(
        self,
        *,
        project_id: str | None = None,
        bucket: str | None = None,
    ) -> list[MemoryRecord]:
        rows = read_jsonl(self.registry_path)
        records = [self._row_to_record(row) for row in rows]
        filtered: list[MemoryRecord] = []
        now = datetime.now(timezone.utc)
        for record in records:
            if project_id is not None and record.project_id != project_id:
                continue
            if bucket is not None and record.bucket != bucket:
                continue
            if record.expires_at is not None and record.expires_at <= now:
                continue
            filtered.append(record)
        filtered.sort(key=lambda item: item.created_at, reverse=True)
        return filtered

    def search(
        self,
        *,
        project_id: str,
        query: str,
        limit: int = 8,
        min_confidence: float = 0.0,
    ) -> list[MemoryRecord]:
        terms = [term.lower() for term in query.split() if term.strip()]
        records = self.list_records(project_id=project_id)
        if not terms:
            return [record for record in records if record.confidence >= min_confidence][:limit]

        scored: list[tuple[float, MemoryRecord]] = []
        now = datetime.now(timezone.utc)
        for record in records:
            if record.confidence < min_confidence:
                continue
            haystack = " ".join([record.summary, " ".join(record.tags), str(record.metadata)]).lower()
            score = float(sum(1 for term in terms if term in haystack))
            if score <= 0:
                continue
            age_days = max(0.0, (now - record.created_at).total_seconds() / 86400)
            recency_bonus = max(0.0, 1.0 - min(age_days, 30.0) / 30.0)
            weighted = score + record.confidence + recency_bonus
            scored.append((weighted, record))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [record for _, record in scored[:limit]]

    @staticmethod
    def _row_to_record(row: dict[str, object]) -> MemoryRecord:
        expires_at = row.get("expires_at")
        return MemoryRecord(
            record_id=str(row.get("record_id", "")),
            project_id=str(row.get("project_id", "")),
            bucket=str(row.get("bucket", "")),
            source_task_id=str(row.get("source_task_id")) if row.get("source_task_id") else None,
            summary=str(row.get("summary", "")),
            confidence=float(row.get("confidence", 0.0) or 0.0),
            created_at=datetime.fromisoformat(str(row.get("created_at"))),
            expires_at=datetime.fromisoformat(str(expires_at)) if expires_at else None,
            tags=tuple(str(item) for item in row.get("tags", []) if str(item).strip()),
            metadata=dict(row.get("metadata", {})),
        )
