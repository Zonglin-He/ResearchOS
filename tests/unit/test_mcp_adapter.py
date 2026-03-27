import asyncio
import socket
import subprocess
import time
from pathlib import Path

from app.tools.mcp_adapter import MCPAdapterTool


REPO_ROOT = Path(__file__).resolve().parents[2]
SERVER_PATH = REPO_ROOT / "tests" / "fixtures" / "mcp_demo_server.py"


def test_mcp_adapter_stdio_lists_and_calls_protocol_objects() -> None:
    tool = MCPAdapterTool()
    common_kwargs = {
        "transport": "stdio",
        "command": "uv",
        "args": ["run", "python", str(SERVER_PATH)],
        "cwd": str(REPO_ROOT),
    }

    tools_result = asyncio.run(tool.execute(operation="list_tools", **common_kwargs))
    tool_names = [item["name"] for item in tools_result["tools"]]

    call_result = asyncio.run(
        tool.execute(
            operation="call_tool",
            name="add",
            arguments={"a": 2, "b": 3},
            **common_kwargs,
        )
    )

    resources_result = asyncio.run(tool.execute(operation="list_resources", **common_kwargs))
    read_resource_result = asyncio.run(
        tool.execute(
            operation="read_resource",
            uri="memo://greeting",
            **common_kwargs,
        )
    )

    prompts_result = asyncio.run(tool.execute(operation="list_prompts", **common_kwargs))
    get_prompt_result = asyncio.run(
        tool.execute(
            operation="get_prompt",
            name="write_intro",
            arguments={"topic": "retrieval systems"},
            **common_kwargs,
        )
    )

    assert "add" in tool_names
    assert call_result["structuredContent"]["result"] == 5
    assert resources_result["resources"][0]["uri"] == "memo://greeting"
    assert read_resource_result["contents"][0]["text"] == "hello from mcp"
    assert prompts_result["prompts"][0]["name"] == "write_intro"
    assert "retrieval systems" in get_prompt_result["messages"][0]["content"]["text"]


def test_mcp_adapter_streamable_http_calls_protocol_objects() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    process = subprocess.Popen(
        ["uv", "run", "python", str(SERVER_PATH), "streamable-http", str(port)],
        cwd=str(REPO_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(4)
        tool = MCPAdapterTool()
        result = asyncio.run(
            tool.execute(
                transport="streamable-http",
                url=f"http://127.0.0.1:{port}/mcp",
                operation="call_tool",
                name="add",
                arguments={"a": 7, "b": 8},
            )
        )
        assert result["structuredContent"]["result"] == 15
    finally:
        process.kill()
        process.wait(timeout=10)
