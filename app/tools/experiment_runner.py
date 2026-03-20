from __future__ import annotations

from app.tools.shell_tool import ShellTool


class ExperimentRunnerTool(ShellTool):
    name = "experiment_runner"
    description = "Run experiment commands and collect their outputs."
    input_schema = {
        "type": "object",
        "properties": {
            "command": {"type": "string"},
            "cwd": {"type": "string"},
            "timeout": {"type": "number"},
        },
        "required": ["command"],
    }
