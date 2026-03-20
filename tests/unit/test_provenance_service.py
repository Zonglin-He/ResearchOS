from pathlib import Path

from app.schemas.artifact import ArtifactRecord
from app.schemas.artifact_annotation import ArtifactAnnotation, ArtifactAnnotationStatus
from app.schemas.claim import Claim
from app.schemas.freeze import ResultsFreeze
from app.schemas.run_manifest import RunManifest
from app.services.artifact_annotation_service import ArtifactAnnotationService
from app.services.artifact_service import ArtifactService
from app.services.audit_service import AuditService
from app.services.claim_service import ClaimService
from app.services.freeze_service import FreezeService
from app.services.provenance_service import ProvenanceService
from app.services.run_service import RunService
from app.services.verification_service import VerificationService


def test_provenance_service_builds_typed_artifact_links(tmp_path: Path) -> None:
    artifact_service = ArtifactService(tmp_path / "registry" / "artifacts.jsonl")
    annotation_service = ArtifactAnnotationService(tmp_path / "registry" / "artifact_annotations.jsonl")
    claim_service = ClaimService(tmp_path / "registry" / "claims.jsonl")
    run_service = RunService(tmp_path / "registry" / "runs.jsonl")
    freeze_service = FreezeService(tmp_path / "registry" / "freezes")
    verification_service = VerificationService(
        run_service=run_service,
        artifact_service=artifact_service,
        claim_service=claim_service,
        freeze_service=freeze_service,
        registry_path=tmp_path / "registry" / "verifications.jsonl",
    )
    audit_service = AuditService(claim_service, run_service)
    provenance_service = ProvenanceService(
        artifact_service=artifact_service,
        annotation_service=annotation_service,
        audit_service=audit_service,
        verification_service=verification_service,
        run_service=run_service,
        claim_service=claim_service,
        freeze_service=freeze_service,
    )

    artifact_path = tmp_path / "artifacts" / "table.csv"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("metric,value\nacc,0.91\n", encoding="utf-8")

    run = RunManifest(
        run_id="run_001",
        spec_id="spec_001",
        git_commit="abc123",
        config_hash="sha256:123",
        dataset_snapshot="dataset_v1",
        seed=7,
        gpu="A100",
        artifacts=["artifact_001"],
    )
    run_service.register_run(run)
    artifact_service.register_artifact(
        ArtifactRecord(
            artifact_id="artifact_001",
            run_id="run_001",
            kind="table",
            path="artifacts/table.csv",
            hash="sha256:table",
            metadata={"table_name": "main_results"},
        )
    )
    claim_service.register_claim(
        Claim(
            claim_id="claim_001",
            text="Model improves robustness",
            claim_type="performance",
            supported_by_runs=["run_001"],
            supported_by_tables=["main_results", "artifact_001"],
            approved_by_human=False,
        )
    )
    freeze_service.save_results_freeze(
        ResultsFreeze(
            results_id="results_001",
            spec_id="spec_001",
            main_claims=["claim_001"],
            tables=["main_results"],
            figures=[],
            approved_by=["operator"],
            status="approved",
        )
    )
    annotation_service.record_annotation(
        ArtifactAnnotation(
            annotation_id="ann_001",
            artifact_id="artifact_001",
            operator="gabriel",
            status=ArtifactAnnotationStatus.REVIEWED,
            review_tags=["important"],
            note="Reviewed by operator.",
        )
    )
    verification_service.verify_run_manifest("run_001")

    artifact, provenance, annotations = provenance_service.build_artifact_provenance("artifact_001")

    assert artifact.artifact_id == "artifact_001"
    assert provenance.run_evidence is not None
    assert provenance.run_evidence.run_id == "run_001"
    assert provenance.exists_on_disk is True
    assert provenance.workspace_relative_path in {"artifacts/table.csv", "artifacts\\table.csv"}
    assert provenance.verification_links[0].subject_id == "run_001"
    assert provenance.audit_subject_refs[0].subject_type == "run"
    assert {ref.support_kind for ref in provenance.claim_support_refs} >= {"run", "table", "artifact"}
    assert provenance.freeze_subject_refs[0].subject_type == "results_freeze"
    assert annotations[0].annotation_id == "ann_001"


def test_provenance_service_builds_audit_and_verification_summaries(tmp_path: Path) -> None:
    artifact_service = ArtifactService(tmp_path / "registry" / "artifacts.jsonl")
    annotation_service = ArtifactAnnotationService(tmp_path / "registry" / "artifact_annotations.jsonl")
    claim_service = ClaimService(tmp_path / "registry" / "claims.jsonl")
    run_service = RunService(tmp_path / "registry" / "runs.jsonl")
    freeze_service = FreezeService(tmp_path / "registry" / "freezes")
    verification_service = VerificationService(
        run_service=run_service,
        artifact_service=artifact_service,
        claim_service=claim_service,
        freeze_service=freeze_service,
        registry_path=tmp_path / "registry" / "verifications.jsonl",
    )
    audit_service = AuditService(claim_service, run_service)
    provenance_service = ProvenanceService(
        artifact_service=artifact_service,
        annotation_service=annotation_service,
        audit_service=audit_service,
        verification_service=verification_service,
        run_service=run_service,
        claim_service=claim_service,
        freeze_service=freeze_service,
    )

    claim_service.register_claim(
        Claim(
            claim_id="claim_002",
            text="Claim references a missing run",
            claim_type="performance",
            supported_by_runs=["missing_run"],
            approved_by_human=False,
        )
    )
    run_service.register_run(
        RunManifest(
            run_id="run_002",
            spec_id="spec_002",
            git_commit="def456",
            config_hash="sha256:456",
            dataset_snapshot="dataset_v2",
            seed=11,
            gpu="L4",
        )
    )
    verification_service.verify_run_manifest("run_002")

    audit_summary = provenance_service.build_audit_summary()
    verification_summary = provenance_service.build_verification_summary()

    assert audit_summary.total_reports >= 2
    assert audit_summary.entry_status_counts["warn"] >= 1
    assert any("missing runs" in finding for finding in audit_summary.findings)
    assert verification_summary.total_checks == 1
    assert verification_summary.status_counts["verified"] == 1
    assert verification_summary.subject_type_counts["run"] == 1
