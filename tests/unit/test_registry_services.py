from datetime import datetime, timezone
from pathlib import Path

from app.schemas.artifact import ArtifactRecord
from app.schemas.claim import Claim
from app.schemas.freeze import ResultsFreeze, SpecFreeze, TopicFreeze
from app.schemas.run_manifest import RunManifest
from app.services.artifact_service import ArtifactService
from app.services.claim_service import ClaimService
from app.services.freeze_service import FreezeService
from app.services.run_service import RunService


def test_claim_service_persists_claims(tmp_path: Path) -> None:
    service = ClaimService(tmp_path / "claims.jsonl")
    claim = Claim(
        claim_id="claim_001",
        text="Method improves robustness",
        claim_type="performance",
        supported_by_runs=["run_001"],
    )

    service.register_claim(claim)
    result = service.get_claim("claim_001")

    assert result is not None
    assert result.claim_id == "claim_001"
    assert result.supported_by_runs == ["run_001"]


def test_run_service_persists_run_manifests(tmp_path: Path) -> None:
    service = RunService(tmp_path / "runs.jsonl")
    manifest = RunManifest(
        run_id="run_001",
        spec_id="spec_001",
        git_commit="abc123",
        config_hash="sha256:123",
        dataset_snapshot="dataset_v1",
        seed=42,
        gpu="A100",
        start_time=datetime.now(timezone.utc),
        status="completed",
        metrics={"accuracy": 0.91},
        artifacts=["runs/logs/run_001.log"],
    )

    service.register_run(manifest)
    result = service.get_run("run_001")

    assert result is not None
    assert result.run_id == "run_001"
    assert result.metrics["accuracy"] == 0.91


def test_artifact_service_persists_artifacts(tmp_path: Path) -> None:
    service = ArtifactService(tmp_path / "artifacts.jsonl")
    artifact = ArtifactRecord(
        artifact_id="artifact_001",
        run_id="run_001",
        kind="figure",
        path="runs/figures/main.png",
        hash="sha256:abc",
        metadata={"format": "png"},
    )

    service.register_artifact(artifact)
    result = service.list_artifacts()

    assert len(result) == 1
    assert result[0].artifact_id == "artifact_001"
    assert result[0].metadata["format"] == "png"


def test_freeze_service_persists_all_freeze_documents(tmp_path: Path) -> None:
    service = FreezeService(tmp_path)

    topic = TopicFreeze(
        topic_id="topic_001",
        selected_gap_ids=["gap_001"],
        research_question="Can purification improve robustness?",
        novelty_type=["setting"],
        owner="gabriel",
    )
    spec = SpecFreeze(
        spec_id="spec_001",
        topic_id="topic_001",
        hypothesis=["Purification improves stability"],
        must_beat_baselines=["EATA"],
    )
    results = ResultsFreeze(
        results_id="results_001",
        spec_id="spec_001",
        main_claims=["claim_001"],
        tables=["writing/tables/main_results.csv"],
    )

    service.save_topic_freeze(topic)
    service.save_spec_freeze(spec)
    service.save_results_freeze(results)

    assert service.load_topic_freeze() == topic
    assert service.load_spec_freeze() == spec
    assert service.load_results_freeze() == results
