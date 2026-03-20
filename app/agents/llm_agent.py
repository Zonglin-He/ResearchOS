from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.agents.base import BaseAgent
from app.providers.base import BaseProvider
from app.schemas.context import RunContext
from app.schemas.result import AgentResult
from app.schemas.task import Task
from app.services.registry_store import to_record
from app.tools.registry import ToolRegistry


class PromptDrivenAgent(BaseAgent):
    prompt_path: str

    def __init__(
        self,
        provider: BaseProvider,
        *,
        model: str | None = None,
        response_schema: dict[str, Any] | None = None,
        tool_registry: ToolRegistry | None = None,
    ) -> None:
        self.provider = provider
        self.model = model
        self.response_schema = response_schema
        self.tool_registry = tool_registry

    async def run(self, task: Task, ctx: RunContext) -> AgentResult:
        system_prompt = Path(self.prompt_path).read_text(encoding="utf-8")
        user_payload = self.build_user_payload(task, ctx)
        output = await self.provider.generate(
            system_prompt=system_prompt,
            user_input=json.dumps(user_payload, ensure_ascii=False, default=str),
            tools=self._tool_definitions(),
            response_schema=self.get_response_schema(task, ctx),
            model=self.model,
        )
        return self.build_result(task, ctx, output)

    def build_user_payload(self, task: Task, ctx: RunContext) -> dict[str, Any]:
        return {
            "task": to_record(task),
            "context": {
                "run_id": ctx.run_id,
                "project_id": ctx.project_id,
                "task_id": ctx.task_id,
                "shared_state": to_record(ctx.shared_state),
                "artifacts_dir": ctx.artifacts_dir,
                "max_steps": ctx.max_steps,
            },
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
