from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from app.providers.command_provider import CommandProvider


class CodexProvider(CommandProvider):
    command_name = "codex"

    def _build_command(
        self,
        prompt: str,
        *,
        response_schema: dict | None,
        model: str | None,
        provider_config: dict | None,
    ) -> tuple[list[str], Path | None]:
        output_path = self._write_temp_text()
        command = [
            "codex",
            "exec",
            "-",
            "--skip-git-repo-check",
            "--output-last-message",
            str(output_path),
        ]
        if model:
            command.extend(["-m", model])
        for key, value in self._iter_provider_config(provider_config):
            command.extend(["-c", f"{key}={value}"])
        if response_schema:
            schema_path = self._write_temp_json(response_schema)
            command.extend(["--output-schema", str(schema_path)])
        return command, output_path

    def _build_stdin_payload(self, prompt: str) -> str | None:
        return prompt

    @staticmethod
    def _iter_provider_config(provider_config: dict | None) -> list[tuple[str, str]]:
        if not isinstance(provider_config, Mapping):
            return []
        normalized: list[tuple[str, str]] = []
        for key, value in provider_config.items():
            if not isinstance(key, str) or not key.strip():
                continue
            normalized.append((key.strip(), CodexProvider._to_toml_literal(value)))
        return normalized

    @staticmethod
    def _to_toml_literal(value: object) -> str:
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, (int, float)):
            return str(value)
        escaped = str(value).replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
