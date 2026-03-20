from __future__ import annotations

import asyncio
import sys

from app.tools.base import BaseTool


class PythonExecTool(BaseTool):
    name = "python_exec"
    description = "Execute Python code in a subprocess."
    input_schema = {
        "type": "object",
        "properties": {
            "code": {"type": "string"},
            "cwd": {"type": "string"},
            "timeout": {"type": "number"},
        },
        "required": ["code"],
    }

    async def execute(self, **kwargs) -> dict:
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-c",
            kwargs["code"],
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
