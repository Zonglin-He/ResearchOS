from __future__ import annotations

from pathlib import Path

from app.providers.command_provider import CommandProvider


class GeminiProvider(CommandProvider):
    command_name = "gemini"

    def _build_command(
        self,
        prompt: str,
        *,
        response_schema: dict | None,
        model: str | None,
    ) -> tuple[list[str], Path | None]:
        command = ["gemini", "-p", prompt, "--output-format", "json"]
        if model:
            command.extend(["--model", model])
        return command, None
