from __future__ import annotations

from datetime import datetime
from pathlib import Path

from app.schemas.verification import (
    VerificationCheckType,
    VerificationRecord,
    VerificationStatus,
)
from app.services.artifact_service import ArtifactService
from app.services.claim_service import ClaimService
from app.services.freeze_service import FreezeService
from app.services.registry_store import append_jsonl, read_jsonl, to_record
from app.services.run_service import RunService


class VerificationService:
    def __init__(
        self,
        *,
        run_service: RunService,
        artifact_service: ArtifactService,
        claim_service: ClaimService,
        freeze_service: FreezeService,
        registry_path: str | Path = "registry/verifications.jsonl",
    ) -> None:
        self.run_service = run_service
        self.artifact_service = artifact_service
        self.claim_service = claim_service
        self.freeze_service = freeze_service
        self.registry_path = Path(registry_path).expanduser().resolve()

    def record_check(self, record: VerificationRecord) -> VerificationRecord:
        append_jsonl(self.registry_path, to_record(record))
        return record

    def list_checks(
        self,
        *,
        subject_type: str | None = None,
        subject_id: str | None = None,
        check_type: VerificationCheckType | str | None = None,
        status: VerificationStatus | str | None = None,
    ) -> list[VerificationRecord]:
        if isinstance(check_type, str):
            check_type = VerificationCheckType(check_type)
        if isinstance(status, str):
            status = VerificationStatus(status)
        checks = self._read_checks()
        filtered: list[VerificationRecord] = []
        for record in checks:
            if subject_type is not None and record.subject_type != subject_type:
                continue
            if subject_id is not None and record.subject_id != subject_id:
                continue
            if check_type is not None and record.check_type != check_type:
                continue
            if status is not None and record.status != status:
                continue
            filtered.append(record)
        return filtered

    def verify_run_manifest(self, run_id: str) -> VerificationRecord:
        run = self.run_service.get_run(run_id)
        if run is None:
            raise KeyError(f"Run not found: {run_id}")

        missing_fields: list[str] = []
        if not run.git_commit:
            missing_fields.append("git_commit")
        if not run.config_hash:
            missing_fields.append("config_hash")
        if not run.dataset_snapshot:
            missing_fields.append("dataset_snapshot")
        if not run.status:
            missing_fields.append("status")

        registered_artifacts = {
            artifact.artifact_id
            for artifact in self.artifact_service.list_artifacts()
            if artifact.run_id == run_id
        }
        missing_artifacts = [
            artifact_id for artifact_id in run.artifacts if artifact_id not in registered_artifacts
        ]
        missing_fields.extend(f"artifact:{artifact_id}" for artifact_id in missing_artifacts)

        if missing_fields:
            status = VerificationStatus.INCOMPLETE
            rationale = "Run manifest is present but missing required fields or registered artifacts."
        else:
            status = VerificationStatus.VERIFIED
            rationale = "Run manifest contains required metadata and referenced artifacts are registered."

        return self.record_check(
            VerificationRecord(
                verification_id=f"verify:run:{run_id}:{len(self._read_checks()) + 1}",
                subject_type="run",
                subject_id=run_id,
                check_type=VerificationCheckType.RUN_MANIFEST_SANITY,
                status=status,
                rationale=rationale,
                evidence_refs=[f"run:{run_id}"],
                artifact_ids=list(run.artifacts),
                missing_fields=missing_fields,
            )
        )

    def verify_claim_evidence(self, claim_id: str) -> VerificationRecord:
        claim = self.claim_service.get_claim(claim_id)
        if claim is None:
            raise KeyError(f"Claim not found: {claim_id}")

        if not claim.supported_by_runs and not claim.supported_by_tables:
            status = VerificationStatus.INCOMPLETE
            rationale = "Claim has no supporting runs or tables recorded."
            missing_fields = ["supported_by_runs", "supported_by_tables"]
        else:
            known_runs = {run.run_id for run in self.run_service.list_runs()}
            missing_run_refs = [
                run_id for run_id in claim.supported_by_runs if run_id not in known_runs
            ]
            if missing_run_refs:
                status = VerificationStatus.FAILED
                rationale = "Claim references runs that do not exist in the run registry."
                missing_fields = [f"supported_run:{run_id}" for run_id in missing_run_refs]
            else:
                status = VerificationStatus.VERIFIED
                rationale = "Claim has explicit run/table support recorded in registries."
                missing_fields = []

        return self.record_check(
            VerificationRecord(
                verification_id=f"verify:claim:{claim_id}:{len(self._read_checks()) + 1}",
                subject_type="claim",
                subject_id=claim_id,
                check_type=VerificationCheckType.CLAIM_EVIDENCE,
                status=status,
                rationale=rationale,
                evidence_refs=[f"claim:{claim_id}", *[f"run:{run_id}" for run_id in claim.supported_by_runs]],
                missing_fields=missing_fields,
            )
        )

    def verify_results_freeze(self) -> VerificationRecord:
        freeze = self.freeze_service.load_results_freeze()
        if freeze is None:
            return self.record_check(
                VerificationRecord(
                    verification_id=f"verify:results-freeze:{len(self._read_checks()) + 1}",
                    subject_type="results_freeze",
                    subject_id="missing",
                    check_type=VerificationCheckType.FREEZE_CONSISTENCY,
                    status=VerificationStatus.NOT_CHECKED,
                    rationale="Results freeze is not present; consistency cannot be checked.",
                )
            )

        spec_freeze = self.freeze_service.load_spec_freeze()
        claim_ids = {claim.claim_id for claim in self.claim_service.list_claims()}
        missing_fields: list[str] = []
        if spec_freeze is None or spec_freeze.spec_id != freeze.spec_id:
            missing_fields.append("spec_freeze")
        missing_claims = [claim_id for claim_id in freeze.main_claims if claim_id not in claim_ids]
        missing_fields.extend(f"claim:{claim_id}" for claim_id in missing_claims)

        if missing_fields:
            status = VerificationStatus.INCOMPLETE
            rationale = "Results freeze does not fully align with spec freeze or registered claims."
        else:
            status = VerificationStatus.VERIFIED
            rationale = "Results freeze aligns with the current spec freeze and registered claims."

        return self.record_check(
            VerificationRecord(
                verification_id=f"verify:results-freeze:{freeze.results_id}:{len(self._read_checks()) + 1}",
                subject_type="results_freeze",
                subject_id=freeze.results_id,
                check_type=VerificationCheckType.FREEZE_CONSISTENCY,
                status=status,
                rationale=rationale,
                evidence_refs=[f"results_freeze:{freeze.results_id}", f"spec_freeze:{freeze.spec_id}"],
                missing_fields=missing_fields,
            )
        )

    def _read_checks(self) -> list[VerificationRecord]:
        rows = read_jsonl(self.registry_path)
        return [
            VerificationRecord(
                verification_id=row["verification_id"],
                subject_type=row["subject_type"],
                subject_id=row["subject_id"],
                check_type=VerificationCheckType(row["check_type"]),
                status=VerificationStatus(row["status"]),
                rationale=row["rationale"],
                evidence_refs=row.get("evidence_refs", []),
                artifact_ids=row.get("artifact_ids", []),
                missing_fields=row.get("missing_fields", []),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]
