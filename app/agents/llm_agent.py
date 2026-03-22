from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.agents.base import BaseAgent
from app.core.prompts import resolve_prompt_path
from app.providers.base import BaseProvider
from app.providers.registry import ProviderRegistry
from app.roles.prompts import ROLE_PROMPT_REGISTRY, RolePromptRegistry
from app.roles.models import AgentRoleBinding
from app.routing.provider_router import ProviderInvocationService
from app.routing.models import AgentRoutingPolicy
from app.schemas.context import RunContext
from app.schemas.result import AgentResult
from app.schemas.task import Task
from app.skills.catalog import ROLE_SKILL_REGISTRY
from app.skills.models import RoleSkillRegistry
from app.services.registry_store import to_record
from app.tools.registry import ToolRegistry


class PromptDrivenAgent(BaseAgent):
    prompt_path: str
    enable_reflection: bool = False

    def __init__(
        self,
        provider: BaseProvider,
        *,
        model: str | None = None,
        response_schema: dict[str, Any] | None = None,
        tool_registry: ToolRegistry | None = None,
        provider_registry: ProviderRegistry | None = None,
        routing_policy: AgentRoutingPolicy | None = None,
        provider_invocation_service: ProviderInvocationService | None = None,
        role_binding: AgentRoleBinding | None = None,
        role_prompt_registry: RolePromptRegistry | None = None,
        role_skill_registry: RoleSkillRegistry | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.response_schema = response_schema
        self.tool_registry = tool_registry
        self.provider_registry = provider_registry
        self.routing_policy = routing_policy
        self.provider_invocation_service = provider_invocation_service
        self.role_binding = role_binding
        self.role_prompt_registry = role_prompt_registry or ROLE_PROMPT_REGISTRY
        self.role_skill_registry = role_skill_registry or ROLE_SKILL_REGISTRY

    async def run(self, task: Task, ctx: RunContext) -> AgentResult:
        system_prompt = self._build_system_prompt(task)
        user_payload = self.build_user_payload(task, ctx)
        user_input = json.dumps(user_payload, ensure_ascii=False, default=str)
        resumed_output = self._resume_output_from_checkpoint(ctx)
        if resumed_output is not None:
            result = self.build_result(task, ctx, resumed_output)
            result.audit_notes.append("resumed from checkpointed llm output")
            return result
        ctx.record_checkpoint(
            "llm_request_prepared",
            {
                "task_id": task.task_id,
                "provider_name": None if ctx.routing is None else ctx.routing.provider_name,
                "model": self._resolve_model(ctx),
            },
        )
        if (
            self.provider_invocation_service is not None
            and self.provider_registry is not None
            and ctx.routing is not None
        ):
            output, final_routing = await self.provider_invocation_service.generate(
                routing=ctx.routing,
                system_prompt=system_prompt,
                user_input=user_input,
                tools=self._tool_definitions(),
                response_schema=self.get_response_schema(task, ctx),
            )
            ctx.routing = final_routing
        else:
            provider = self._resolve_provider(ctx)
            output = await provider.generate(
                system_prompt=system_prompt,
                user_input=user_input,
                tools=self._tool_definitions(),
                response_schema=self.get_response_schema(task, ctx),
                model=self._resolve_model(ctx),
            )
        if self.enable_reflection:
            output = await self._reflect_output(task, ctx, output)
        ctx.record_checkpoint(
            "llm_response_received",
            {
                "task_id": task.task_id,
                "output": output,
            },
        )
        result = self.build_result(task, ctx, output)
        ctx.record_checkpoint(
            "agent_result_built",
            {
                "task_id": task.task_id,
                "result_status": result.status,
                "output": output,
                "artifact_count": len(result.artifacts),
                "next_task_count": len(result.next_tasks),
            },
        )
        role_asset_note = self._build_role_asset_audit_note(task)
        if role_asset_note is not None:
            result.audit_notes.append(role_asset_note)
        return result

    async def _reflect_output(
        self,
        task: Task,
        ctx: RunContext,
        output: dict[str, Any],
    ) -> dict[str, Any]:
        critique_schema = self.get_response_schema(task, ctx)
        critique_prompt = (
            "You are auditing a structured agent output before it is committed. "
            "Check for unsupported conclusions, missing evidence, logical jumps, "
            "or incomplete required fields. Return a corrected version in the same schema. "
            "If the draft is already acceptable, preserve it and add audit_notes that reflection passed."
        )
        critique_input = json.dumps(
            {
                "task_kind": task.kind,
                "draft_output": output,
                "required_schema": critique_schema,
            },
            ensure_ascii=False,
            default=str,
        )
        if (
            self.provider_invocation_service is not None
            and self.provider_registry is not None
            and ctx.routing is not None
        ):
            reflected, final_routing = await self.provider_invocation_service.generate(
                routing=ctx.routing,
                system_prompt=critique_prompt,
                user_input=critique_input,
                tools=None,
                response_schema=critique_schema,
            )
            ctx.routing = final_routing
            return reflected
        provider = self._resolve_provider(ctx)
        return await provider.generate(
            system_prompt=critique_prompt,
            user_input=critique_input,
            tools=None,
            response_schema=critique_schema,
            model=self._resolve_model(ctx),
        )

    @staticmethod
    def _resume_output_from_checkpoint(ctx: RunContext) -> dict[str, Any] | None:
        checkpoint = ctx.resume_from_checkpoint
        if not isinstance(checkpoint, dict):
            return None
        payload = checkpoint.get("payload")
        if not isinstance(payload, dict):
            return None
        output = payload.get("output")
        if isinstance(output, dict) and output:
            return output
        return None

    def _resolve_provider(self, ctx: RunContext) -> BaseProvider:
        if ctx.routing is not None and self.provider_registry is not None:
            return self.provider_registry.get(ctx.routing.provider_name)
        return self.provider

    def _resolve_model(self, ctx: RunContext) -> str | None:
        if ctx.routing is not None and ctx.routing.model is not None:
            return ctx.routing.model
        return self.model

    def build_user_payload(self, task: Task, ctx: RunContext) -> dict[str, Any]:
        return {
            "task": to_record(task),
            "context": {
                "run_id": ctx.run_id,
                "project_id": ctx.project_id,
                "task_id": ctx.task_id,
                "shared_state": to_record(ctx.shared_state),
                "artifacts_dir": ctx.artifacts_dir,
                "checkpoint_dir": ctx.checkpoint_dir,
                "checkpoint_path": ctx.checkpoint_path,
                "resume_from_checkpoint": ctx.resume_from_checkpoint,
                "max_steps": ctx.max_steps,
                "routing": to_record(ctx.routing),
                "prior_lessons": to_record(ctx.prior_lessons),
            },
            "role_contract": self._build_role_contract(task),
            "role_assets": self._build_role_assets_metadata(task),
        }

    def get_response_schema(
        self,
        task: Task,
        ctx: RunContext,
    ) -> dict[str, Any] | None:
        return self.response_schema

    def build_result(
        self,
        task: Task,
        ctx: RunContext,
        output: dict[str, Any],
    ) -> AgentResult:
        return AgentResult(status="success", output=output)

    def _tool_definitions(self) -> list[dict[str, Any]] | None:
        if self.tool_registry is None:
            return None
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema,
            }
            for tool in self.tool_registry.list_tools()
        ]

    def _build_role_contract(self, task: Task) -> dict[str, Any] | None:
        if self.role_binding is None:
            return None
        role = self.role_binding.resolve_role(task.kind)
        role_spec = self.role_binding.resolve_role_spec(task.kind)
        return {
            "agent_name": self.role_binding.agent_name,
            "resolved_role": role.value,
            "secondary_roles": [role.value for role in self.role_binding.secondary_roles],
            "artifact_contracts": self.role_binding.expected_artifact_types(task.kind),
            "role_spec": None if role_spec is None else role_spec.to_contract_record(),
            "secondary_role_specs": [
                spec.to_contract_record() for spec in self.role_binding.secondary_role_specs()
            ],
        }

    def _build_role_assets_metadata(self, task: Task) -> dict[str, Any] | None:
        if self.role_binding is None:
            return None
        role_spec = self.role_binding.resolve_role_spec(task.kind)
        if role_spec is None:
            return None
        prompt_spec = (
            None
            if self.role_prompt_registry is None
            else self.role_prompt_registry.get_for_role(role_spec.role_id)
        )
        skills = []
        if self.role_skill_registry is not None:
            for skill_name in role_spec.canonical_skill_names:
                skill = self.role_skill_registry.get(skill_name)
                if skill is not None:
                    skills.append(skill.to_metadata_record())
        return {
            "prompt": None if prompt_spec is None else prompt_spec.to_metadata_record(),
            "skills": skills,
        }

    def _build_system_prompt(self, task: Task) -> str:
        specialized_prompt = resolve_prompt_path(self.prompt_path).read_text(encoding="utf-8").strip()
        if self.role_binding is None or self.role_prompt_registry is None:
            return specialized_prompt

        role_spec = self.role_binding.resolve_role_spec(task.kind)
        if role_spec is None:
            return specialized_prompt

        role_prompt = self.role_prompt_registry.require_for_role(role_spec.role_id).load_text()
        return "\n\n".join(
            [
                "ResearchOS canonical role contract prompt:",
                role_prompt,
                "ResearchOS specialized agent adapter:",
                specialized_prompt,
            ]
        ).strip()

    def _build_role_asset_audit_note(self, task: Task) -> str | None:
        if self.role_binding is None:
            return None
        role_spec = self.role_binding.resolve_role_spec(task.kind)
        if role_spec is None:
            return None
        return (
            "role assets resolved "
            f"role={role_spec.role_name} "
            f"prompt={role_spec.canonical_prompt_id or '<none>'} "
            f"skills={list(role_spec.canonical_skill_names)}"
        )
