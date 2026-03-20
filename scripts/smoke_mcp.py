from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

from app.tools.mcp_adapter import MCPAdapterTool


def main() -> int:
    tool = MCPAdapterTool()
    common = {
        "transport": "stdio",
        "command": "uv",
        "args": ["run", "python", "tests/fixtures/mcp_demo_server.py"],
        "cwd": str(Path.cwd()),
    }
    tools_result = asyncio.run(tool.execute(operation="list_tools", **common))
    call_result = asyncio.run(
        tool.execute(
            operation="call_tool",
            name="add",
            arguments={"a": 10, "b": 5},
            **common,
        )
    )
    resources_result = asyncio.run(tool.execute(operation="list_resources", **common))
    prompts_result = asyncio.run(tool.execute(operation="list_prompts", **common))

    report = {
        "ran_at": datetime.now(timezone.utc).isoformat(),
        "tools": tools_result["tools"],
        "call_tool": call_result,
        "resources": resources_result["resources"],
        "prompts": prompts_result["prompts"],
    }
    output_path = Path("artifacts/mcp_smoke_report.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
