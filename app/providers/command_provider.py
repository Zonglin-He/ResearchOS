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
        return self._parse_response(raw_output, response_schema=response_schema)

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
        timeout_seconds = self._timeout_seconds(provider_config)
        max_attempts = self._max_attempts(provider_config)
        errors: list[str] = []
        for attempt in range(max_attempts):
            if attempt > 0:
                await asyncio.sleep(min(8, 2 ** (attempt - 1)))
            try:
                stdout_text = await self._invoke_once(
                    resolved_command,
                    stdin_bytes,
                    output_path=output_path,
                    timeout_seconds=timeout_seconds,
                )
            except RuntimeError as error:
                errors.append(str(error))
                continue
            if stdout_text.strip():
                return stdout_text.strip()
            errors.append(f"{self.command_name} provider returned empty output")
        raise RuntimeError(errors[-1] if errors else f"{self.command_name} provider failed")

    async def _invoke_once(
        self,
        resolved_command: list[str],
        stdin_bytes: bytes | None,
        *,
        output_path: Path | None,
        timeout_seconds: int,
    ) -> str:
        try:
            process = await asyncio.create_subprocess_exec(
                *resolved_command,
                stdin=asyncio.subprocess.PIPE if stdin_bytes is not None else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, stderr = await asyncio.wait_for(process.communicate(stdin_bytes), timeout=timeout_seconds)
            except asyncio.TimeoutError as error:
                process.kill()
                await process.communicate()
                raise RuntimeError(
                    f"{self.command_name} provider timed out after {timeout_seconds}s"
                ) from error
        except NotImplementedError:
            stdout, stderr, returncode = await asyncio.to_thread(
                self._invoke_blocking,
                resolved_command,
                stdin_bytes,
                timeout_seconds,
            )
            if returncode != 0:
                raise RuntimeError(
                    f"{self.command_name} provider failed: {stderr.strip() or 'subprocess returned a non-zero exit code'}"
                )
            stdout_text = stdout.strip()
        else:
            if process.returncode != 0:
                raise RuntimeError(
                    f"{self.command_name} provider failed: {self._decode_output(stderr).strip() or 'subprocess returned a non-zero exit code'}"
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
        timeout_seconds: int,
    ) -> tuple[str, str, int]:
        try:
            completed = subprocess.run(
                resolved_command,
                input=stdin_bytes,
                capture_output=True,
                check=False,
                timeout=timeout_seconds,
            )
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(
                f"{self.command_name} provider timed out after {timeout_seconds}s"
            ) from error
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

    def _parse_response(
        self,
        raw_output: str,
        *,
        response_schema: dict[str, Any] | None,
    ) -> dict[str, Any]:
        normalized = self._normalize_raw_output(raw_output)
        if not normalized:
            return self._coerce_payload("", response_schema=response_schema)

        for candidate in self._iter_json_candidates(normalized):
            try:
                payload = json.loads(candidate)
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict):
                return self._coerce_payload(payload, response_schema=response_schema)
            return self._coerce_payload({"content": payload}, response_schema=response_schema)
        return self._coerce_payload(normalized, response_schema=response_schema)

    def _coerce_payload(
        self,
        payload: dict[str, Any] | str,
        *,
        response_schema: dict[str, Any] | None,
    ) -> dict[str, Any]:
        if response_schema is None:
            return payload if isinstance(payload, dict) else {"content": str(payload)}

        properties = response_schema.get("properties", {})
        result = dict(payload) if isinstance(payload, dict) else {}
        fallback_text = result.get("content") if isinstance(result.get("content"), str) else str(payload)

        for key, spec in properties.items():
            if key in result:
                continue
            value_type = spec.get("type")
            if value_type == "array":
                result[key] = []
            elif value_type == "object":
                result[key] = {}
            elif value_type == "integer":
                result[key] = 0
            elif value_type == "number":
                result[key] = 0.0
            elif value_type == "boolean":
                result[key] = False
            elif key in {"assistant_message", "summary", "revised_markdown"}:
                result[key] = fallback_text.strip()
            else:
                result[key] = ""

        required = response_schema.get("required", [])
        for key in required:
            result.setdefault(key, [] if properties.get(key, {}).get("type") == "array" else "")
        return result

    @staticmethod
    def _timeout_seconds(provider_config: dict[str, Any] | None) -> int:
        if isinstance(provider_config, dict):
            try:
                return max(10, int(provider_config.get("timeout_seconds", 120)))
            except (TypeError, ValueError):
                pass
        return 120

    @staticmethod
    def _max_attempts(provider_config: dict[str, Any] | None) -> int:
        if isinstance(provider_config, dict):
            try:
                return max(1, int(provider_config.get("max_attempts", 3)))
            except (TypeError, ValueError):
                pass
        return 3

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
