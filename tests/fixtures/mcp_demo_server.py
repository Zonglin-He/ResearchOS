from __future__ import annotations

import sys

from mcp.server.fastmcp import FastMCP


def build_server(port: int = 8765) -> FastMCP:
    server = FastMCP(
        "ResearchOS MCP Demo",
        port=port,
        json_response=True,
        stateless_http=True,
    )

    @server.tool()
    def add(a: int, b: int) -> int:
        return a + b

    @server.resource("memo://greeting")
    def greeting() -> str:
        return "hello from mcp"

    @server.prompt()
    def write_intro(topic: str) -> str:
        return f"Write a concise introduction about {topic}."

    return server


if __name__ == "__main__":
    transport = sys.argv[1] if len(sys.argv) > 1 else "stdio"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8765
    build_server(port).run(transport=transport)
