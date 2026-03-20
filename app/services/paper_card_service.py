from __future__ import annotations

from pathlib import Path

from app.schemas.paper_card import EvidenceRef, PaperCard
from app.services.registry_store import append_jsonl, read_jsonl, to_record


class PaperCardService:
    def __init__(self, registry_path: str | Path = "registry/paper_cards.jsonl") -> None:
        self.registry_path = Path(registry_path).expanduser().resolve()

    def register_card(self, card: PaperCard) -> PaperCard:
        append_jsonl(self.registry_path, to_record(card))
        return card

    def get_card(self, paper_id: str) -> PaperCard | None:
        for card in self.list_cards():
            if card.paper_id == paper_id:
                return card
        return None

    def list_cards(self) -> list[PaperCard]:
        rows = read_jsonl(self.registry_path)
        return [
            PaperCard(
                paper_id=row["paper_id"],
                title=row["title"],
                problem=row["problem"],
                setting=row["setting"],
                task_type=row["task_type"],
                core_assumption=row.get("core_assumption", []),
                method_summary=row.get("method_summary", ""),
                key_modules=row.get("key_modules", []),
                datasets=row.get("datasets", []),
                metrics=row.get("metrics", []),
                strongest_result=row.get("strongest_result", ""),
                claimed_contributions=row.get("claimed_contributions", []),
                hidden_dependencies=row.get("hidden_dependencies", []),
                likely_failure_modes=row.get("likely_failure_modes", []),
                repro_risks=row.get("repro_risks", []),
                idea_seeds=row.get("idea_seeds", []),
                evidence_refs=[
                    EvidenceRef(section=ref["section"], page=ref["page"])
                    for ref in row.get("evidence_refs", [])
                ],
            )
            for row in rows
        ]
