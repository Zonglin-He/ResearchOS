from __future__ import annotations

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
    ) -> tuple[list[str], Path | None]:
        output_path = self._write_temp_text()
        command = [
            "codex",
            "exec",
            prompt,
            "--skip-git-repo-check",
            "--output-last-message",
            str(output_path),
        ]
        if model:
            command.extend(["-m", model])
        if response_schema:
            schema_path = self._write_temp_json(response_schema)
            command.extend(["--output-schema", str(schema_path)])
        return command, output_path
