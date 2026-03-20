from __future__ import annotations

from app.agents.llm_agent import PromptDrivenAgent
from app.agents.response_schemas import VERIFIER_RESPONSE_SCHEMA
from app.agents.utils import write_artifact
from app.roles import verifier_role_binding
from app.schemas.result import AgentResult
from app.schemas.task import Task
from app.services.artifact_service import ArtifactService
from app.services.verification_service import VerificationService


class VerifierAgent(PromptDrivenAgent):
    name = "verifier_agent"
    description = "Verifies evidence chains and methodological validity."
    prompt_path = "C:/Anti Project/ResearchOS/prompts/verifier.md"
    role_binding = verifier_role_binding()

    def __init__(
        self,
        provider,
        *,
        verification_service: VerificationService | None = None,
        artifact_service: ArtifactService | None = None,
        model: str | None = None,
        tool_registry=None,
        provider_registry=None,
        routing_policy=None,
        provider_invocation_service=None,
    ) -> None:
        super().__init__(
            provider,
            model=model,
            response_schema=VERIFIER_RESPONSE_SCHEMA,
            tool_registry=tool_registry,
            provider_registry=provider_registry,
            routing_policy=routing_policy,
            provider_invocation_service=provider_invocation_service,
            role_binding=self.role_binding,
        )
        self.verification_service = verification_service
        self.artifact_service = artifact_service

    def build_result(self, task: Task, ctx, output: dict) -> AgentResult:
        verification_record = self._run_verification(task)
        lines = [
            f"# Verification Report for {task.task_id}",
            "",
            output.get("summary", verification_record.rationale),
            "",
            f"- verification_id: {verification_record.verification_id}",
            f"- status: {verification_record.status.value}",
            f"- check_type: {verification_record.check_type.value}",
        ]
        if output.get("recommendations"):
            lines.append("")
            lines.append("## Recommendations")
            lines.extend(f"- {item}" for item in output["recommendations"])
        artifact = write_artifact(
            run_id=ctx.run_id,
            artifact_id=f"{ctx.run_id}-verification-report",
            kind="verification_report",
            content="\n".join(lines) + "\n",
            extension="md",
            metadata={
                "verification_id": verification_record.verification_id,
                "subject_type": verification_record.subject_type,
                "subject_id": verification_record.subject_id,
            },
            artifacts_dir=ctx.artifacts_dir or "artifacts",
        )
        if self.artifact_service is not None:
            self.artifact_service.register_artifact(artifact)
        return AgentResult(
            status="success",
            output={
                "summary": output.get("summary", verification_record.rationale),
                "verification_id": verification_record.verification_id,
                "verification_status": verification_record.status.value,
                "verification_report_path": artifact.path,
            },
            artifacts=[artifact.artifact_id],
            audit_notes=output.get("audit_notes", []) + [verification_record.rationale],
        )

    def _run_verification(self, task: Task):
        if self.verification_service is None:
            raise ValueError("VerifierAgent requires verification_service")
        if run_id := task.input_payload.get("run_id"):
            return self.verification_service.verify_run_manifest(run_id)
        if claim_id := task.input_payload.get("claim_id"):
            return self.verification_service.verify_claim_evidence(claim_id)
        return self.verification_service.verify_results_freeze()
