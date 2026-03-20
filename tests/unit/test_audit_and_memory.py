from datetime import datetime, timezone
from pathlib import Path

from app.memory.project_memory import ProjectMemory
from app.memory.retrieval import ProjectMemoryRetrieval
from app.schemas.claim import Claim
from app.schemas.gap_map import GapMap
from app.schemas.paper_card import PaperCard
from app.schemas.run_manifest import RunManifest
from app.services.audit_service import AuditService
from app.services.claim_service import ClaimService
from app.services.run_service import RunService


def test_project_memory_and_retrieval() -> None:
    memory = ProjectMemory(project_id="p1")
    memory.add_paper_card(
        PaperCard(
            paper_id="paper_001",
            title="A Paper",
            problem="Robustness",
            setting="Streaming shift",
            task_type="classification",
        )
    )
    memory.add_gap_map(GapMap(topic="robustness"))
    memory.add_note("Promising gap around streaming adaptation.")

    retrieval = ProjectMemoryRetrieval(memory)

    assert len(memory.paper_cards) == 1
    assert len(memory.gap_maps) == 1
    assert retrieval.search_notes("streaming") == ["Promising gap around streaming adaptation."]


def test_audit_service_fails_for_missing_runs(tmp_path: Path) -> None:
    claim_service = ClaimService(tmp_path / "claims.jsonl")
    run_service = RunService(tmp_path / "runs.jsonl")
    claim_service.register_claim(
        Claim(
            claim_id="claim_001",
            text="Model improves accuracy",
            claim_type="performance",
            supported_by_runs=["run_missing"],
            approved_by_human=False,
        )
    )
    run_service.register_run(
        RunManifest(
            run_id="run_001",
            spec_id="spec_001",
            git_commit="abc123",
            config_hash="sha256:123",
            dataset_snapshot="dataset_v1",
            seed=42,
            gpu="A100",
            start_time=datetime.now(timezone.utc),
            status="completed",
        )
    )

    report = AuditService(claim_service, run_service).build_claim_alignment_report()

    assert report.status == "fail"
    assert "missing runs" in report.findings[0]
    assert "should be reviewed" in report.recommendations[0]
