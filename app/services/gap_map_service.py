from __future__ import annotations

from pathlib import Path

from app.schemas.gap_map import Gap, GapCluster, GapMap
from app.services.registry_store import append_jsonl, read_jsonl, to_record


class GapMapService:
    def __init__(self, registry_path: str | Path = "registry/gap_maps.jsonl") -> None:
        self.registry_path = Path(registry_path)

    def register_gap_map(self, gap_map: GapMap) -> GapMap:
        append_jsonl(self.registry_path, to_record(gap_map))
        return gap_map

    def list_gap_maps(self) -> list[GapMap]:
        rows = read_jsonl(self.registry_path)
        return [
            GapMap(
                topic=row["topic"],
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
            for row in rows
        ]
