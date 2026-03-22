from __future__ import annotations

import json
import os
import platform
import re
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
from app.tools.experiment_runner import run_experiment
from app.services.artifact_service import ArtifactService
from app.services.claim_service import ClaimService
from app.services.run_service import RunService
from app.agents.utils import write_artifact


class BuilderAgent(PromptDrivenAgent):
    name = "builder_agent"
    description = "Builds code and experiments from a frozen spec."
    prompt_path = "prompts/builder.md"
    enable_reflection = True
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
        payload["context"]["hardware"] = self._hardware_context()
        return payload

    def build_result(self, task: Task, ctx, output: dict[str, Any]) -> AgentResult:
        experiment_script = self._inject_checkpoint_hooks(str(output.get("experiment_script", "")).strip())
        execution_command = str(output.get("execution_command", "")).strip() or "python experiment.py"
        script_artifact = None
        execution_result = None
        execution_metrics: dict[str, Any] = {}
        if experiment_script:
            script_artifact = write_artifact(
                run_id=ctx.run_id,
                artifact_id=f"{ctx.run_id}-experiment",
                kind="experiment_script",
                content=experiment_script,
                extension="py",
                metadata={"execution_command": execution_command},
                artifacts_dir=ctx.artifacts_dir or "artifacts",
            )
            if self.artifact_service is not None:
                self.artifact_service.register_artifact(script_artifact)
            timeout_seconds = self._execution_timeout(task)
            execution_result = run_experiment(
                script_artifact.path,
                timeout=timeout_seconds,
                checkpoint_dir=ctx.checkpoint_dir or ctx.artifacts_dir or "artifacts",
                max_rounds=int(task.input_payload.get("repair_rounds", 5)),
            )
            execution_metrics = self._extract_metrics(execution_result["stdout"])

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
            status=self._manifest_status(run_payload.get("status", "completed"), execution_result),
            metrics={**run_payload.get("metrics", {}), **execution_metrics},
            artifacts=run_payload.get("artifacts", []),
            dispatch_routing=ctx.routing,
        )
        if self.run_service is not None:
            self.run_service.register_run(manifest)

        artifact_ids = []
        if script_artifact is not None:
            artifact_ids.append(script_artifact.artifact_id)

        if execution_result is not None:
            execution_artifact = write_artifact(
                run_id=ctx.run_id,
                artifact_id=f"{ctx.run_id}-execution-log",
                kind="execution_log",
                content=json.dumps(execution_result, ensure_ascii=False, indent=2),
                extension="json",
                metadata={"execution_command": execution_command},
                artifacts_dir=ctx.artifacts_dir or "artifacts",
            )
            if self.artifact_service is not None:
                self.artifact_service.register_artifact(execution_artifact)
            artifact_ids.append(execution_artifact.artifact_id)

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
                kind="analyze_run",
                goal=f"Analyze build outputs for run {manifest.run_id}",
                input_payload={
                    "run_id": manifest.run_id,
                    "claim_ids": claim_ids,
                    "artifact_ids": artifact_ids,
                    "stdout": None if execution_result is None else execution_result["stdout"],
                    "stderr": None if execution_result is None else execution_result["stderr"],
                    "returncode": None if execution_result is None else execution_result["returncode"],
                    "metrics": manifest.metrics,
                },
                assigned_agent="analyst_agent",
            )
        ]

        return AgentResult(
            status="success",
            output={
                "summary": output.get("summary", ""),
                "experiment_script": experiment_script,
                "execution_result": execution_result,
                "run_manifest": run_payload,
                "claims": output.get("claims", []),
                "artifacts": output.get("artifacts", []),
            },
            artifacts=artifact_ids,
            next_tasks=next_tasks,
            audit_notes=output.get("audit_notes", []),
        )

    @staticmethod
    def _execution_timeout(task: Task) -> int:
        try:
            return max(30, int(task.input_payload.get("timeout_seconds", 600)))
        except (TypeError, ValueError):
            return 600

    @staticmethod
    def _manifest_status(base_status: str, execution_result: dict[str, Any] | None) -> str:
        if execution_result is None:
            return base_status
        return "completed" if execution_result.get("returncode") == 0 else "failed"

    @staticmethod
    def _extract_metrics(stdout: str) -> dict[str, Any]:
        metrics: dict[str, Any] = {}
        json_match = re.search(r"\{[\s\S]*\}", stdout)
        if json_match is not None:
            try:
                parsed = json.loads(json_match.group(0))
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                return parsed
        for key, value in re.findall(r"([A-Za-z_][A-Za-z0-9_\-]*)\s*[:=]\s*(-?\d+(?:\.\d+)?)", stdout):
            metrics[key] = float(value)
        return metrics

    @staticmethod
    def _hardware_context() -> dict[str, Any]:
        context = {
            "platform": platform.system(),
            "cpu_cores": os.cpu_count() or 1,
            "gpu_available": False,
            "gpu_name": None,
            "gpu_memory_gb": 0.0,
        }
        try:
            import torch  # type: ignore

            if torch.cuda.is_available():
                props = torch.cuda.get_device_properties(0)
                context["gpu_available"] = True
                context["gpu_name"] = torch.cuda.get_device_name(0)
                context["gpu_memory_gb"] = round(props.total_memory / 1e9, 2)
        except Exception:
            pass
        return context

    @staticmethod
    def _inject_checkpoint_hooks(script: str) -> str:
        if not script or "_save_checkpoint" in script:
            return script
        prelude = """
import json
import os
_ckpt_dir = os.environ.get("RESEARCHOS_CHECKPOINT_DIR", ".")
os.makedirs(_ckpt_dir, exist_ok=True)
def _save_checkpoint(epoch, metrics):
    with open(os.path.join(_ckpt_dir, f"epoch_{epoch}.json"), "w", encoding="utf-8") as _f:
        json.dump(metrics, _f, ensure_ascii=False, indent=2)
"""
        return prelude.strip() + "\n\n" + script
