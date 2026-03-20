from __future__ import annotations

from app.tools.shell_tool import ShellTool


class GitTool(ShellTool):
    name = "git"
    description = "Run safe git read operations."
    input_schema = {
        "type": "object",
        "properties": {
            "git_args": {"type": "array", "items": {"type": "string"}},
            "cwd": {"type": "string"},
        },
        "required": ["git_args"],
    }

    async def execute(self, **kwargs) -> dict:
        command = "git " + " ".join(kwargs["git_args"])
        return await super().execute(command=command, cwd=kwargs.get("cwd"))
