from __future__ import annotations

import asyncio
import json
import socket
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from app.tools.mcp_adapter import MCPAdapterTool


REPO_ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    process = subprocess.Popen(
        ["uv", "run", "python", str(REPO_ROOT / "tests" / "fixtures" / "mcp_demo_server.py"), "streamable-http", str(port)],
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(4)
        tool = MCPAdapterTool()
        tools_result = asyncio.run(
            tool.execute(
                transport="streamable-http",
                url=f"http://127.0.0.1:{port}/mcp",
                operation="list_tools",
            )
        )
        call_result = asyncio.run(
            tool.execute(
                transport="streamable-http",
                url=f"http://127.0.0.1:{port}/mcp",
                operation="call_tool",
                name="add",
                arguments={"a": 6, "b": 9},
            )
        )
        report = {
            "ran_at": datetime.now(timezone.utc).isoformat(),
            "tools": tools_result["tools"],
            "call_tool": call_result,
        }
        output_path = Path("artifacts/mcp_streamable_http_smoke_report.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0
    finally:
        process.kill()
        process.wait(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
