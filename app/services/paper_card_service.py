from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.db.sqlite import SQLiteDatabase
from app.schemas.paper_card import EvidenceRef, PaperCard
from app.services.registry_store import append_jsonl, read_jsonl, to_record


class PaperCardService:
    def __init__(
        self,
        registry_path: str | Path = "registry/paper_cards.jsonl",
        *,
        database: SQLiteDatabase | None = None,
    ) -> None:
        self.registry_path = Path(registry_path).expanduser().resolve()
        self.database = database

    def register_card(self, card: PaperCard) -> PaperCard:
        append_jsonl(self.registry_path, to_record(card))
        if self.database is not None:
            with self.database.connect() as connection:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO paper_cards (paper_id, title, task_type, record_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        card.paper_id,
                        card.title,
                        card.task_type,
                        json.dumps(to_record(card), ensure_ascii=False),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
        return card

    def get_card(self, paper_id: str) -> PaperCard | None:
        if self.database is not None:
            self._hydrate_database_if_needed()
            with self.database.connect() as connection:
                row = connection.execute(
                    "SELECT record_json FROM paper_cards WHERE paper_id = ?",
                    (paper_id,),
                ).fetchone()
            if row is not None:
                return self._row_to_card(json.loads(row["record_json"]))
        for card in self.list_cards():
            if card.paper_id == paper_id:
                return card
        return None

    def list_cards(self) -> list[PaperCard]:
        if self.database is not None:
            self._hydrate_database_if_needed()
            with self.database.connect() as connection:
                rows = connection.execute(
                    "SELECT record_json FROM paper_cards ORDER BY created_at, paper_id"
                ).fetchall()
            return [self._row_to_card(json.loads(row["record_json"])) for row in rows]
        rows = read_jsonl(self.registry_path)
        return [self._row_to_card(row) for row in rows]

    def _hydrate_database_if_needed(self) -> None:
        if self.database is None:
            return
        with self.database.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM paper_cards").fetchone()
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
                    INSERT OR REPLACE INTO paper_cards (paper_id, title, task_type, record_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        row["paper_id"],
                        row["title"],
                        row["task_type"],
                        json.dumps(row, ensure_ascii=False),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )

    @staticmethod
    def _row_to_card(row: dict[str, object]) -> PaperCard:
        return [
            PaperCard(
                paper_id=str(row["paper_id"]),
                title=str(row["title"]),
                problem=str(row["problem"]),
                setting=str(row["setting"]),
                task_type=str(row["task_type"]),
                core_assumption=list(row.get("core_assumption", [])),
                method_summary=str(row.get("method_summary", "")),
                key_modules=list(row.get("key_modules", [])),
                datasets=list(row.get("datasets", [])),
                metrics=list(row.get("metrics", [])),
                strongest_result=str(row.get("strongest_result", "")),
                claimed_contributions=list(row.get("claimed_contributions", [])),
                hidden_dependencies=list(row.get("hidden_dependencies", [])),
                likely_failure_modes=list(row.get("likely_failure_modes", [])),
                repro_risks=list(row.get("repro_risks", [])),
                idea_seeds=list(row.get("idea_seeds", [])),
                evidence_refs=[
                    EvidenceRef(section=ref["section"], page=ref["page"])
                    for ref in row.get("evidence_refs", [])
                ],
            )
        ][0]
