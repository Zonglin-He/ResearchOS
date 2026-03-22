from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from app.services.registry_store import append_jsonl, read_jsonl


@dataclass
class KnowledgeRecord:
    record_id: str
    project_id: str
    title: str
    summary: str
    context_tags: list[str] = field(default_factory=list)
    payload: dict[str, object] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class KnowledgeBaseService:
    def __init__(self, root: str | Path = "registry/kb") -> None:
        self.root = Path(root).expanduser().resolve()

    def record_decision(self, record: KnowledgeRecord) -> KnowledgeRecord:
        self._append("decisions.jsonl", record)
        return record

    def record_finding(self, record: KnowledgeRecord) -> KnowledgeRecord:
        self._append("findings.jsonl", record)
        return record

    def record_literature(self, record: KnowledgeRecord) -> KnowledgeRecord:
        self._append("literature.jsonl", record)
        return record

    def record_open_question(self, record: KnowledgeRecord) -> KnowledgeRecord:
        self._append("open_questions.jsonl", record)
        return record

    def search_findings(self, query: str, limit: int = 5) -> list[dict[str, object]]:
        return self._search("findings.jsonl", query, limit)

    def search_decisions(self, query: str, limit: int = 3) -> list[dict[str, object]]:
        return self._search("decisions.jsonl", query, limit)

    def list_bucket(self, bucket: str, limit: int = 20) -> list[KnowledgeRecord]:
        rows = read_jsonl(self.root / f"{bucket}.jsonl")
        return [self._row_to_record(row) for row in rows[-limit:]]

    def _append(self, filename: str, record: KnowledgeRecord) -> None:
        append_jsonl(
            self.root / filename,
            {
                "record_id": record.record_id,
                "project_id": record.project_id,
                "title": record.title,
                "summary": record.summary,
                "context_tags": list(record.context_tags),
                "payload": dict(record.payload),
                "created_at": record.created_at.isoformat(),
            },
        )

    def _search(self, filename: str, query: str, limit: int) -> list[dict[str, object]]:
        terms = [term.lower() for term in query.split() if term.strip()]
        rows = read_jsonl(self.root / filename)
        scored: list[tuple[int, dict[str, object]]] = []
        for row in rows:
            haystack = " ".join(
                [
                    str(row.get("title", "")),
                    str(row.get("summary", "")),
                    " ".join(str(tag) for tag in row.get("context_tags", [])),
                ]
            ).lower()
            score = sum(1 for term in terms if term in haystack)
            if score:
                scored.append((score, row))
        scored.sort(key=lambda item: item[0], reverse=True)
        return [row for _, row in scored[:limit]]

    @staticmethod
    def _row_to_record(row: dict[str, object]) -> KnowledgeRecord:
        return KnowledgeRecord(
            record_id=str(row.get("record_id", "")),
            project_id=str(row.get("project_id", "")),
            title=str(row.get("title", "")),
            summary=str(row.get("summary", "")),
            context_tags=[str(item) for item in row.get("context_tags", [])],
            payload=dict(row.get("payload", {})),
            created_at=datetime.fromisoformat(str(row.get("created_at"))),
        )
