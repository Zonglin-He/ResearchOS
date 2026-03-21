from __future__ import annotations

import asyncio
import json
import locale
import re
import shutil
import subprocess
import tempfile
from abc import abstractmethod
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from app.providers.base import BaseProvider


class CommandProvider(BaseProvider):
    command_name: str

    async def generate(
        self,
        system_prompt: str,
        user_input: str,
        tools: list[dict[str, Any]] | None = None,
        response_schema: dict[str, Any] | None = None,
        model: str | None = None,
        provider_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        prompt = self._build_prompt(system_prompt, user_input, tools)
        raw_output = await self._invoke(
            prompt,
            response_schema=response_schema,
            model=model,
            provider_config=provider_config,
        )
        return self._parse_response(raw_output)

    def _build_prompt(
        self,
        system_prompt: str,
        user_input: str,
        tools: list[dict[str, Any]] | None,
    ) -> str:
        prompt = (
            "Follow the role contract and complete the task.\n"
            "Return only the final answer requested by the task.\n\n"
            "<role_contract>\n"
            f"{system_prompt}\n"
            "</role_contract>\n\n"
            "<task_input>\n"
            f"{user_input}\n"
            "</task_input>"
        )
        if tools:
            prompt += (
                "\n\n<available_tools>\n"
                f"{json.dumps(tools, ensure_ascii=False, indent=2)}\n"
                "</available_tools>"
            )
        return prompt

    async def _invoke(
        self,
        prompt: str,
        *,
        response_schema: dict[str, Any] | None,
        model: str | None,
        provider_config: dict[str, Any] | None,
    ) -> str:
        command, output_path = self._build_command(
            prompt,
            response_schema=response_schema,
            model=model,
            provider_config=provider_config,
        )
        resolved_command = self._resolve_command(command)
        stdin_payload = self._build_stdin_payload(prompt)
        stdin_bytes = None if stdin_payload is None else stdin_payload.encode("utf-8")
        try:
            process = await asyncio.create_subprocess_exec(
                *resolved_command,
                stdin=asyncio.subprocess.PIPE if stdin_bytes is not None else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate(stdin_bytes)
        except NotImplementedError:
            stdout, stderr, returncode = await asyncio.to_thread(
                self._invoke_blocking,
                resolved_command,
                stdin_bytes,
            )
            if returncode != 0:
                raise RuntimeError(
                    f"{self.command_name} provider failed: {stderr.strip() or 'subprocess returned a non-zero exit code'}"
                )
            stdout_text = stdout.strip()
        else:
            if process.returncode != 0:
                raise RuntimeError(
                    f"{self.command_name} provider failed: {self._decode_output(stderr).strip()}"
                )
            stdout_text = self._decode_output(stdout).strip()
        if output_path is not None and output_path.exists():
            file_output = output_path.read_text(encoding="utf-8").strip()
            if file_output:
                return file_output
        return stdout_text

    def _invoke_blocking(
        self,
        resolved_command: list[str],
        stdin_bytes: bytes | None,
    ) -> tuple[str, str, int]:
        try:
            completed = subprocess.run(
                resolved_command,
                input=stdin_bytes,
                capture_output=True,
                check=False,
            )
        except OSError as error:
            raise RuntimeError(f"{self.command_name} provider failed: {error}") from error
        return (
            self._decode_output(completed.stdout),
            self._decode_output(completed.stderr),
            completed.returncode,
        )

    def _decode_output(self, output: bytes | str | None) -> str:
        if output is None:
            return ""
        if isinstance(output, str):
            return output
        candidates = [
            "utf-8",
            locale.getpreferredencoding(False) or "utf-8",
            "cp936",
            "gbk",
        ]
        for encoding in candidates:
            try:
                return output.decode(encoding)
            except UnicodeDecodeError:
                continue
        return output.decode("utf-8", errors="replace")

    def _resolve_command(self, command: list[str]) -> list[str]:
        executable = command[0]
        resolved = shutil.which(executable) or executable
        if resolved.lower().endswith(".ps1"):
            shell = shutil.which("pwsh") or shutil.which("powershell") or "powershell"
            return [
                shell,
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-File",
                resolved,
                *command[1:],
            ]
        return [resolved, *command[1:]]

    def _build_stdin_payload(self, prompt: str) -> str | None:
        return None

    def _parse_response(self, raw_output: str) -> dict[str, Any]:
        normalized = self._normalize_raw_output(raw_output)
        if not normalized:
            return {}

        for candidate in self._iter_json_candidates(normalized):
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return payload
            return {"content": payload}
        return {"content": normalized}

    def _normalize_raw_output(self, raw_output: str) -> str:
        return raw_output.strip()

    def _iter_json_candidates(self, raw_output: str) -> Iterator[str]:
        yield raw_output
        for match in re.finditer(r"```(?:json)?\s*(.+?)```", raw_output, flags=re.DOTALL):
            yield match.group(1).strip()
        extracted = self._extract_balanced_json(raw_output)
        if extracted is not None and extracted != raw_output:
            yield extracted

    def _extract_balanced_json(self, raw_output: str) -> str | None:
        start = None
        depth = 0
        in_string = False
        escape = False

        for index, char in enumerate(raw_output):
            if escape:
                escape = False
                continue
            if char == "\\":
                escape = True
                continue
            if char == '"':
                in_string = not in_string
                continue
            if in_string:
                continue
            if char in "{[":
                if depth == 0:
                    start = index
                depth += 1
            elif char in "}]":
                if depth == 0:
                    continue
                depth -= 1
                if depth == 0 and start is not None:
                    return raw_output[start : index + 1].strip()
        return None

    @abstractmethod
    def _build_command(
        self,
        prompt: str,
        *,
        response_schema: dict[str, Any] | None,
        model: str | None,
        provider_config: dict[str, Any] | None,
    ) -> tuple[list[str], Path | None]:
        ...

    def _write_temp_json(self, payload: dict[str, Any]) -> Path:
        temp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        with temp:
            json.dump(payload, temp, ensure_ascii=False)
        return Path(temp.name)

    def _write_temp_text(self) -> Path:
        temp = tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False, encoding="utf-8")
        temp.close()
        return Path(temp.name)
