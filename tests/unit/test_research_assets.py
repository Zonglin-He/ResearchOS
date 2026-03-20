from pathlib import Path

from app.schemas.approval import Approval
from app.schemas.gap_map import Gap, GapCluster, GapMap
from app.schemas.paper_card import EvidenceRef, PaperCard
from app.services.approval_service import ApprovalService
from app.services.gap_map_service import GapMapService
from app.services.paper_card_service import PaperCardService


def test_paper_card_service_roundtrip(tmp_path: Path) -> None:
    service = PaperCardService(tmp_path / "paper_cards.jsonl")
    card = PaperCard(
        paper_id="paper_001",
        title="A Paper",
        problem="Robustness",
        setting="Streaming shift",
        task_type="classification",
        evidence_refs=[EvidenceRef(section="method", page=4)],
    )

    service.register_card(card)
    result = service.get_card("paper_001")

    assert result is not None
    assert result.paper_id == "paper_001"
    assert result.evidence_refs[0].page == 4


def test_gap_map_service_roundtrip(tmp_path: Path) -> None:
    service = GapMapService(tmp_path / "gap_maps.jsonl")
    gap_map = GapMap(
        topic="test-time adaptation",
        clusters=[
            GapCluster(
                name="assumption fragility",
                gaps=[
                    Gap(
                        gap_id="gap_001",
                        description="Methods assume stable statistics",
                    )
                ],
            )
        ],
    )

    service.register_gap_map(gap_map)
    result = service.list_gap_maps()

    assert len(result) == 1
    assert result[0].clusters[0].gaps[0].gap_id == "gap_001"


def test_approval_service_lists_pending_items(tmp_path: Path) -> None:
    service = ApprovalService(tmp_path / "approvals.jsonl")
    service.record_approval(
        Approval(
            approval_id="approval_001",
            project_id="p1",
            target_type="freeze",
            target_id="spec_001",
            approved_by="gabriel",
            decision="pending",
        )
    )

    pending = service.list_pending()

    assert len(pending) == 1
    assert pending[0].approval_id == "approval_001"
