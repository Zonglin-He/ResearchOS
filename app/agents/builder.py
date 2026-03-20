from __future__ import annotations

from typing import Any

from app.agents.llm_agent import PromptDrivenAgent
from app.agents.response_schemas import BUILDER_RESPONSE_SCHEMA
from app.agents.utils import build_child_task
from app.roles import builder_role_binding
from app.schemas.artifact import ArtifactRecord
from app.schemas.claim import Claim
from app.schemas.result import AgentResult
from app.schemas.run_manifest import RunManifest
from app.schemas.task import Task
from app.services.artifact_service import ArtifactService
from app.services.claim_service import ClaimService
from app.services.run_service import RunService


class BuilderAgent(PromptDrivenAgent):
    name = "builder_agent"
    description = "Builds code and experiments from a frozen spec."
    prompt_path = "C:/Anti Project/ResearchOS/prompts/builder.md"
    role_binding = builder_role_binding()

    def __init__(
        self,
        provider,
        *,
        artifact_service: ArtifactService | None = None,
        claim_service: ClaimService | None = None,
        run_service: RunService | None = None,
        model: str | None = None,
        tool_registry=None,
        provider_registry=None,
        routing_policy=None,
        provider_invocation_service=None,
        role_prompt_registry=None,
        role_skill_registry=None,
    ) -> None:
        super().__init__(
            provider,
            model=model,
            response_schema=BUILDER_RESPONSE_SCHEMA,
            tool_registry=tool_registry,
            provider_registry=provider_registry,
            routing_policy=routing_policy,
            provider_invocation_service=provider_invocation_service,
            role_binding=self.role_binding,
            role_prompt_registry=role_prompt_registry,
            role_skill_registry=role_skill_registry,
        )
        self.artifact_service = artifact_service
        self.claim_service = claim_service
        self.run_service = run_service

    def build_user_payload(self, task, ctx) -> dict[str, Any]:
        payload = super().build_user_payload(task, ctx)
        payload["builder_focus"] = {
            "required_outputs": ["summary", "run_manifest", "artifacts", "claims"],
            "hard_constraints": [
                "do not change baseline fairness constraints",
                "do not redefine metrics without explicit approval",
                "surface every executable artifact explicitly",
            ],
        }
        return payload

    def build_result(self, task: Task, ctx, output: dict[str, Any]) -> AgentResult:
        run_payload = output["run_manifest"]
        manifest = RunManifest(
            run_id=run_payload["run_id"],
            spec_id=run_payload["spec_id"],
            git_commit=run_payload["git_commit"],
            config_hash=run_payload["config_hash"],
            dataset_snapshot=run_payload["dataset_snapshot"],
            seed=run_payload["seed"],
            gpu=run_payload["gpu"],
            experiment_proposal_id=task.experiment_proposal_id,
            experiment_branch=run_payload.get("experiment_branch") or task.input_payload.get("branch_name"),
            status=run_payload.get("status", "completed"),
            metrics=run_payload.get("metrics", {}),
            artifacts=run_payload.get("artifacts", []),
            dispatch_routing=ctx.routing,
        )
        if self.run_service is not None:
            self.run_service.register_run(manifest)

        artifact_ids = []
        for item in output.get("artifacts", []):
            artifact = ArtifactRecord(
                artifact_id=item["artifact_id"],
                run_id=ctx.run_id,
                kind=item["kind"],
                path=item["path"],
                hash=item["hash"],
                metadata=item.get("metadata", {}),
            )
            if self.artifact_service is not None:
                self.artifact_service.register_artifact(artifact)
            artifact_ids.append(artifact.artifact_id)

        claim_ids = []
        for item in output.get("claims", []):
            claim = Claim(
                claim_id=item["claim_id"],
                text=item["text"],
                claim_type=item["claim_type"],
                supported_by_runs=[manifest.run_id],
                supported_by_tables=item.get("supported_by_tables", []),
                risk_level=item.get("risk_level", "medium"),
            )
            if self.claim_service is not None:
                self.claim_service.register_claim(claim)
            claim_ids.append(claim.claim_id)

        next_tasks = [
            build_child_task(
                task,
                kind="review_build",
                goal=f"Review build outputs for run {manifest.run_id}",
                input_payload={
                    "run_id": manifest.run_id,
                    "claim_ids": claim_ids,
                    "artifact_ids": artifact_ids,
                },
                assigned_agent="reviewer_agent",
            )
        ]

        return AgentResult(
            status="success",
            output={
                "summary": output.get("summary", ""),
                "run_manifest": run_payload,
                "claims": output.get("claims", []),
                "artifacts": output.get("artifacts", []),
            },
            artifacts=artifact_ids,
            next_tasks=next_tasks,
            audit_notes=output.get("audit_notes", []),
        )
