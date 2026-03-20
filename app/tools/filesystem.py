from __future__ import annotations

from pathlib import Path

from app.tools.base import BaseTool


class FilesystemTool(BaseTool):
    name = "filesystem"
    description = "Read, write, and list files in the workspace."
    input_schema = {
        "type": "object",
        "properties": {
            "action": {"type": "string"},
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["action", "path"],
    }

    async def execute(self, **kwargs) -> dict:
        action = kwargs["action"]
        path = Path(kwargs["path"])

        if action == "read_text":
            return {"content": path.read_text(encoding="utf-8")}
        if action == "write_text":
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(kwargs.get("content", ""), encoding="utf-8")
            return {"path": str(path)}
        if action == "list_dir":
            return {"items": [str(item) for item in path.iterdir()]}
        raise ValueError(f"Unsupported filesystem action: {action}")
