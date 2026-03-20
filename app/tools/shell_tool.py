from __future__ import annotations

import asyncio

from app.tools.base import BaseTool


class ShellTool(BaseTool):
    name = "shell"
    description = "Run shell commands and return stdout/stderr."
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "cwd": {"type": "string"},
            "timeout": {"type": "number"},
        },
        "required": ["command"],
    }

    async def execute(self, **kwargs) -> dict:
        process = await asyncio.create_subprocess_shell(
            kwargs["command"],
            cwd=kwargs.get("cwd"),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        timeout = kwargs.get("timeout", 30)
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=timeout)
        return {
            "returncode": process.returncode,
            "stdout": stdout.decode("utf-8"),
            "stderr": stderr.decode("utf-8"),
        }
