from app.schemas.audit import AuditEntry, AuditReport, AuditSummary
from app.schemas.verification import VerificationRecord
from app.services.claim_service import ClaimService
from app.services.run_service import RunService
from app.services.verification_service import VerificationService


class AuditService:
    def __init__(self, claim_service: ClaimService, run_service: RunService) -> None:
        self.claim_service = claim_service
        self.run_service = run_service

    def build_claim_alignment_report(self) -> AuditReport:
        findings: list[str] = []
        recommendations: list[str] = []
        entries: list[AuditEntry] = []

        runs = {run.run_id for run in self.run_service.list_runs()}
        for claim in self.claim_service.list_claims():
            missing_runs = [run_id for run_id in claim.supported_by_runs if run_id not in runs]
            if missing_runs:
                rationale = f"Claim {claim.claim_id} references missing runs: {', '.join(missing_runs)}"
                findings.append(rationale)
                entries.append(
                    AuditEntry(
                        entry_id=f"audit:claim:{claim.claim_id}:missing-runs",
                        subject_type="claim",
                        subject_id=claim.claim_id,
                        category="claim_alignment",
                        status="fail",
                        rationale=rationale,
                        evidence_refs=[f"claim:{claim.claim_id}"],
                        related_run_ids=missing_runs,
                        related_claim_ids=[claim.claim_id],
                    )
                )
            if not claim.approved_by_human:
                recommendation = f"Claim {claim.claim_id} should be reviewed and approved before writing."
                recommendations.append(recommendation)
                entries.append(
                    AuditEntry(
                        entry_id=f"audit:claim:{claim.claim_id}:approval",
                        subject_type="claim",
                        subject_id=claim.claim_id,
                        category="claim_approval",
                        status="warn",
                        rationale=recommendation,
                        evidence_refs=[f"claim:{claim.claim_id}"],
                        related_claim_ids=[claim.claim_id],
                    )
                )

        status = "pass" if not findings else "fail"
        return AuditReport(
            report_type="claim_alignment_report",
            status=status,
            findings=findings,
            recommendations=recommendations,
            entries=entries,
        )

    def build_run_verification_report(
        self,
        run_id: str,
        verification_service: VerificationService,
    ) -> AuditReport:
        verification = verification_service.verify_run_manifest(run_id)
        return self.build_run_verification_report_from_record(run_id, verification)

    def list_artifact_entries(
        self,
        artifact_id: str,
        *,
        run_id: str,
        verification_service: VerificationService,
    ) -> list[AuditEntry]:
        entries: list[AuditEntry] = []
        for verification in verification_service.list_checks_for_artifact(artifact_id, run_id=run_id):
            entries.extend(self.build_run_verification_report_from_record(run_id, verification).entries)
        return entries

    def build_summary(self, verification_service: VerificationService) -> AuditSummary:
        reports = [self.build_claim_alignment_report()]
        for verification in verification_service.list_checks(subject_type="run"):
            reports.append(
                self.build_run_verification_report_from_record(
                    verification.subject_id,
                    verification,
                )
            )

        report_status_counts: dict[str, int] = {}
        entry_status_counts: dict[str, int] = {}
        findings: list[str] = []
        recommendations: list[str] = []
        total_entries = 0
        for report in reports:
            report_status_counts[report.status] = report_status_counts.get(report.status, 0) + 1
            findings.extend(report.findings)
            recommendations.extend(report.recommendations)
            total_entries += len(report.entries)
            for entry in report.entries:
                entry_status_counts[entry.status] = entry_status_counts.get(entry.status, 0) + 1

        return AuditSummary(
            total_reports=len(reports),
            total_entries=total_entries,
            report_status_counts=report_status_counts,
            entry_status_counts=entry_status_counts,
            findings=findings,
            recommendations=recommendations,
        )

    def build_run_verification_report_from_record(
        self,
        run_id: str,
        verification: VerificationRecord,
    ) -> AuditReport:
        status = "pass" if verification.status.value == "verified" else "warn"
        return AuditReport(
            report_type="run_verification_report",
            status=status,
            findings=[] if status == "pass" else [verification.rationale],
            recommendations=[] if status == "pass" else ["Complete missing run metadata or register referenced artifacts."],
            entries=[
                AuditEntry(
                    entry_id=f"audit:run:{run_id}:{verification.check_type.value}",
                    subject_type="run",
                    subject_id=run_id,
                    category=verification.check_type.value,
                    status=verification.status.value,
                    rationale=verification.rationale,
                    evidence_refs=verification.evidence_refs,
                    artifact_ids=verification.artifact_ids,
                    related_run_ids=[run_id],
                )
            ],
        )
