from app.schemas.audit import AuditReport
from app.services.claim_service import ClaimService
from app.services.run_service import RunService


class AuditService:
    def __init__(self, claim_service: ClaimService, run_service: RunService) -> None:
        self.claim_service = claim_service
        self.run_service = run_service

    def build_claim_alignment_report(self) -> AuditReport:
        findings: list[str] = []
        recommendations: list[str] = []

        runs = {run.run_id for run in self.run_service.list_runs()}
        for claim in self.claim_service.list_claims():
            missing_runs = [run_id for run_id in claim.supported_by_runs if run_id not in runs]
            if missing_runs:
                findings.append(
                    f"Claim {claim.claim_id} references missing runs: {', '.join(missing_runs)}"
                )
            if not claim.approved_by_human:
                recommendations.append(
                    f"Claim {claim.claim_id} should be reviewed and approved before writing."
                )

        status = "pass" if not findings else "fail"
        return AuditReport(
            report_type="claim_alignment_report",
            status=status,
            findings=findings,
            recommendations=recommendations,
        )
