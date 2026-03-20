from dataclasses import dataclass, field

from app.schemas.gap_map import GapMap
from app.schemas.paper_card import PaperCard


@dataclass
class ProjectMemory:
    project_id: str
    paper_cards: list[PaperCard] = field(default_factory=list)
    gap_maps: list[GapMap] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def add_paper_card(self, paper_card: PaperCard) -> None:
        self.paper_cards.append(paper_card)

    def add_gap_map(self, gap_map: GapMap) -> None:
        self.gap_maps.append(gap_map)

    def add_note(self, note: str) -> None:
        self.notes.append(note)
