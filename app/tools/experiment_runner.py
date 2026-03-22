from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any

from app.tools.base import BaseTool


def run_experiment(script_path: str, timeout: int = 600) -> dict[str, Any]:
    completed = subprocess.run(
        [sys.executable, script_path],
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    return {
        "stdout": completed.stdout[-5000:],
        "stderr": completed.stderr[-2000:],
        "returncode": completed.returncode,
    }


class ExperimentRunnerTool(BaseTool):
    name = "experiment_runner"
    description = "Run a local Python experiment script and collect stdout/stderr."
    input_schema = {
        "type": "object",
        "properties": {
            "script_path": {"type": "string"},
            "timeout": {"type": "integer"},
        },
        "required": ["script_path"],
    }

    async def execute(self, **kwargs) -> dict[str, Any]:
        script_path = str(kwargs["script_path"]).strip()
        timeout = int(kwargs.get("timeout", 600))
        return run_experiment(script_path, timeout=timeout)
