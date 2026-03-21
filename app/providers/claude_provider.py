from __future__ import annotations

import json
from pathlib import Path

from app.providers.command_provider import CommandProvider


class ClaudeProvider(CommandProvider):
    command_name = "claude"

    def _build_command(
        self,
        prompt: str,
        *,
        response_schema: dict | None,
        model: str | None,
        provider_config: dict | None,
    ) -> tuple[list[str], Path | None]:
        command = ["claude", "-p", prompt, "--output-format", "json"]
        if model:
            command.extend(["--model", model])
        if response_schema:
            command.extend(["--json-schema", self._write_temp_json(response_schema).read_text(encoding="utf-8")])
        return command, None

    def _normalize_raw_output(self, raw_output: str) -> str:
        normalized = super()._normalize_raw_output(raw_output)
        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError:
            return normalized
        if isinstance(payload, dict) and isinstance(payload.get("result"), str):
            return payload["result"].strip()
        return normalized
