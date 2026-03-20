from __future__ import annotations

from app.schemas.artifact import ArtifactRecord
from app.schemas.artifact_annotation import ArtifactAnnotation
from app.schemas.audit import AuditSummary
from app.schemas.provenance import (
    ArtifactProvenance,
    AuditSubjectRef,
    ClaimSupportRef,
    ProvenanceEvidenceRef,
    RunEvidenceRef,
    VerificationLink,
)
from app.schemas.verification import VerificationSummary
from app.services.artifact_annotation_service import ArtifactAnnotationService
from app.services.artifact_service import ArtifactService
from app.services.audit_service import AuditService
from app.services.claim_service import ClaimService
from app.services.freeze_service import FreezeService
from app.services.run_service import RunService
from app.services.verification_service import VerificationService


class ProvenanceService:
    def __init__(
        self,
        *,
        artifact_service: ArtifactService,
        annotation_service: ArtifactAnnotationService,
        audit_service: AuditService,
        verification_service: VerificationService,
        run_service: RunService,
        claim_service: ClaimService,
        freeze_service: FreezeService,
    ) -> None:
        self.artifact_service = artifact_service
        self.annotation_service = annotation_service
        self.audit_service = audit_service
        self.verification_service = verification_service
        self.run_service = run_service
        self.claim_service = claim_service
        self.freeze_service = freeze_service

    def build_artifact_provenance(
        self,
        artifact_id: str,
    ) -> tuple[ArtifactRecord, ArtifactProvenance, list[ArtifactAnnotation]]:
        artifact = self.artifact_service.get_artifact(artifact_id)
        if artifact is None:
            raise KeyError(f"Artifact not found: {artifact_id}")

        resolved_path = self.artifact_service.resolve_artifact_path(artifact)
        workspace_root = self.artifact_service.workspace_root
        try:
            workspace_relative_path = str(resolved_path.relative_to(workspace_root))
        except ValueError:
            workspace_relative_path = None

        verification_links = [
            VerificationLink(
                verification_id=record.verification_id,
                subject_type=record.subject_type,
                subject_id=record.subject_id,
                check_type=record.check_type.value,
                status=record.status.value,
                rationale=record.rationale,
                evidence_refs=[self._parse_evidence_ref(raw_ref) for raw_ref in record.evidence_refs],
                artifact_ids=record.artifact_ids,
                missing_fields=record.missing_fields,
            )
            for record in self.verification_service.list_checks_for_artifact(
                artifact_id,
                run_id=artifact.run_id,
            )
        ]
        audit_subject_refs = [
            AuditSubjectRef(
                subject_type=entry.subject_type,
                subject_id=entry.subject_id,
                category=entry.category,
                status=entry.status,
                rationale=entry.rationale,
                entry_id=entry.entry_id,
                evidence_refs=[self._parse_evidence_ref(raw_ref) for raw_ref in entry.evidence_refs],
                artifact_ids=entry.artifact_ids,
            )
            for entry in self.audit_service.list_artifact_entries(
                artifact_id,
                run_id=artifact.run_id,
                verification_service=self.verification_service,
            )
        ]

        run = self.run_service.get_run(artifact.run_id)
        run_evidence = None
        if run is not None:
            run_evidence = RunEvidenceRef(
                run_id=run.run_id,
                spec_id=run.spec_id,
                status=run.status,
                artifact_ids=run.artifacts,
            )

        claim_support_refs: list[ClaimSupportRef] = []
        table_alias = artifact.metadata.get("table_name")
        for claim in self.claim_service.list_claims():
            if artifact.run_id in claim.supported_by_runs:
                claim_support_refs.append(
                    ClaimSupportRef(
                        claim_id=claim.claim_id,
                        support_kind="run",
                        support_value=artifact.run_id,
                    )
                )
            if artifact.artifact_id in claim.supported_by_tables:
                claim_support_refs.append(
                    ClaimSupportRef(
                        claim_id=claim.claim_id,
                        support_kind="artifact",
                        support_value=artifact.artifact_id,
                    )
                )
            if table_alias and table_alias in claim.supported_by_tables:
                claim_support_refs.append(
                    ClaimSupportRef(
                        claim_id=claim.claim_id,
                        support_kind="table",
                        support_value=table_alias,
                    )
                )

        freeze_subject_refs: list[AuditSubjectRef] = []
        results_freeze = self.freeze_service.load_results_freeze()
        if results_freeze is not None and run is not None and results_freeze.spec_id == run.spec_id:
            freeze_subject_refs.append(
                AuditSubjectRef(
                    subject_type="results_freeze",
                    subject_id=results_freeze.results_id,
                    category="freeze_context",
                    status=results_freeze.status,
                    rationale="Artifact belongs to a run under the current results freeze spec.",
                )
            )

        provenance = ArtifactProvenance(
            artifact_id=artifact.artifact_id,
            run_id=artifact.run_id,
            resolved_path=str(resolved_path),
            workspace_relative_path=workspace_relative_path,
            exists_on_disk=resolved_path.exists(),
            run_evidence=run_evidence,
            verification_links=verification_links,
            audit_subject_refs=audit_subject_refs,
            claim_support_refs=claim_support_refs,
            freeze_subject_refs=freeze_subject_refs,
        )
        annotations = self.annotation_service.list_annotations(artifact_id)
        return artifact, provenance, annotations

    def build_verification_summary(self) -> VerificationSummary:
        links = [
            VerificationLink(
                verification_id=record.verification_id,
                subject_type=record.subject_type,
                subject_id=record.subject_id,
                check_type=record.check_type.value,
                status=record.status.value,
                rationale=record.rationale,
                evidence_refs=[self._parse_evidence_ref(raw_ref) for raw_ref in record.evidence_refs],
                artifact_ids=record.artifact_ids,
                missing_fields=record.missing_fields,
            )
            for record in self.verification_service.list_checks()
        ]
        status_counts: dict[str, int] = {}
        check_type_counts: dict[str, int] = {}
        subject_type_counts: dict[str, int] = {}
        for link in links:
            status_counts[link.status] = status_counts.get(link.status, 0) + 1
            check_type_counts[link.check_type] = check_type_counts.get(link.check_type, 0) + 1
            subject_type_counts[link.subject_type] = subject_type_counts.get(link.subject_type, 0) + 1
        return VerificationSummary(
            total_checks=len(links),
            status_counts=status_counts,
            check_type_counts=check_type_counts,
            subject_type_counts=subject_type_counts,
        )

    def build_audit_summary(self) -> AuditSummary:
        reports = [self.audit_service.build_claim_alignment_report()]
        for record in self.verification_service.list_checks(subject_type="run"):
            reports.append(
                self.audit_service.build_run_verification_report_from_record(
                    record.subject_id,
                    record,
                )
            )
        audit_refs = [
            AuditSubjectRef(
                subject_type=entry.subject_type,
                subject_id=entry.subject_id,
                category=entry.category,
                status=entry.status,
                rationale=entry.rationale,
                entry_id=entry.entry_id,
                evidence_refs=[self._parse_evidence_ref(raw_ref) for raw_ref in entry.evidence_refs],
                artifact_ids=entry.artifact_ids,
            )
            for report in reports
            for entry in report.entries
        ]
        report_status_counts: dict[str, int] = {}
        entry_status_counts: dict[str, int] = {}
        findings: list[str] = []
        recommendations: list[str] = []
        for report in reports:
            report_status_counts[report.status] = report_status_counts.get(report.status, 0) + 1
            findings.extend(report.findings)
            recommendations.extend(report.recommendations)
        for ref in audit_refs:
            entry_status_counts[ref.status] = entry_status_counts.get(ref.status, 0) + 1
        return AuditSummary(
            total_reports=len(reports),
            total_entries=len(audit_refs),
            report_status_counts=report_status_counts,
            entry_status_counts=entry_status_counts,
            findings=findings,
            recommendations=recommendations,
        )

    @staticmethod
    def _parse_evidence_ref(raw_ref: str) -> ProvenanceEvidenceRef:
        if ":" in raw_ref:
            ref_type, ref_id = raw_ref.split(":", 1)
            return ProvenanceEvidenceRef(ref_type=ref_type, ref_id=ref_id, raw_ref=raw_ref)
        return ProvenanceEvidenceRef(ref_type="unknown", ref_id=raw_ref, raw_ref=raw_ref)
