from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from app.db.sqlite import SQLiteDatabase
from app.schemas.gap_map import Gap, GapCluster, GapMap
from app.services.registry_store import append_jsonl, read_jsonl, to_record


class GapMapService:
    def __init__(
        self,
        registry_path: str | Path = "registry/gap_maps.jsonl",
        *,
        database: SQLiteDatabase | None = None,
    ) -> None:
        self.registry_path = Path(registry_path).expanduser().resolve()
        self.database = database

    def register_gap_map(self, gap_map: GapMap) -> GapMap:
        append_jsonl(self.registry_path, to_record(gap_map))
        if self.database is not None:
            with self.database.connect() as connection:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO gap_maps (topic, record_json, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (
                        gap_map.topic,
                        json.dumps(to_record(gap_map), ensure_ascii=False),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )
        return gap_map

    def get_gap_map(self, topic: str) -> GapMap | None:
        if self.database is not None:
            self._hydrate_database_if_needed()
            with self.database.connect() as connection:
                row = connection.execute(
                    "SELECT record_json FROM gap_maps WHERE topic = ?",
                    (topic,),
                ).fetchone()
            if row is not None:
                return self._row_to_gap_map(json.loads(row["record_json"]))
        matches = [gap_map for gap_map in self.list_gap_maps() if gap_map.topic == topic]
        if not matches:
            return None
        return matches[-1]

    def list_gap_maps(self) -> list[GapMap]:
        if self.database is not None:
            self._hydrate_database_if_needed()
            with self.database.connect() as connection:
                rows = connection.execute(
                    "SELECT record_json FROM gap_maps ORDER BY created_at, topic"
                ).fetchall()
            return [self._row_to_gap_map(json.loads(row["record_json"])) for row in rows]
        rows = read_jsonl(self.registry_path)
        return [self._row_to_gap_map(row) for row in rows]

    def _hydrate_database_if_needed(self) -> None:
        if self.database is None:
            return
        with self.database.connect() as connection:
            row = connection.execute("SELECT COUNT(*) AS count FROM gap_maps").fetchone()
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
                    INSERT OR REPLACE INTO gap_maps (topic, record_json, created_at)
                    VALUES (?, ?, ?)
                    """,
                    (
                        row["topic"],
                        json.dumps(row, ensure_ascii=False),
                        datetime.now(timezone.utc).isoformat(),
                    ),
                )

    @staticmethod
    def _row_to_gap_map(row: dict[str, object]) -> GapMap:
        return [
            GapMap(
                topic=str(row["topic"]),
                clusters=[
                    GapCluster(
                        name=cluster["name"],
                        gaps=[
                            Gap(
                                gap_id=gap["gap_id"],
                                description=gap["description"],
                                supporting_papers=gap.get("supporting_papers", []),
                                attack_surface=gap.get("attack_surface", ""),
                                difficulty=gap.get("difficulty", ""),
                                novelty_type=gap.get("novelty_type", ""),
                            )
                            for gap in cluster.get("gaps", [])
                        ],
                    )
                    for cluster in row.get("clusters", [])
                ],
            )
        ][0]
