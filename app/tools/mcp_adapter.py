from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.shared.version import LATEST_PROTOCOL_VERSION
from pydantic import AnyUrl, TypeAdapter

from app.tools.base import BaseTool

MCP_SESSION_ID_HEADER = "mcp-session-id"
MCP_PROTOCOL_VERSION_HEADER = "mcp-protocol-version"


class MCPAdapterTool(BaseTool):
    name = "mcp_adapter"
    description = "Connect to a real MCP server and interact with tools, resources, and prompts."
    input_schema = {
        "type": "object",
        "properties": {
            "transport": {
                "type": "string",
                "enum": ["stdio", "streamable-http"],
            },
            "operation": {
                "type": "string",
                "enum": [
                    "list_tools",
                    "call_tool",
                    "list_resources",
                    "read_resource",
                    "list_prompts",
                    "get_prompt",
                ],
            },
            "command": {"type": "string"},
            "args": {"type": "array", "items": {"type": "string"}},
            "env": {"type": "object"},
            "cwd": {"type": "string"},
            "url": {"type": "string"},
            "headers": {"type": "object"},
            "name": {"type": "string"},
            "arguments": {"type": "object"},
            "uri": {"type": "string"},
        },
        "required": ["operation"],
    }

    async def execute(self, **kwargs) -> dict[str, Any]:
        if kwargs.get("transport", "stdio") == "streamable-http":
            return await self._execute_streamable_http(**kwargs)

        async with self._open_session(**kwargs) as session:
            await session.initialize()
            operation = kwargs["operation"]

            if operation == "list_tools":
                result = await session.list_tools()
                return result.model_dump(mode="json")

            if operation == "call_tool":
                result = await session.call_tool(
                    kwargs["name"],
                    arguments=kwargs.get("arguments"),
                )
                return result.model_dump(mode="json")

            if operation == "list_resources":
                result = await session.list_resources()
                return result.model_dump(mode="json")

            if operation == "read_resource":
                uri = TypeAdapter(AnyUrl).validate_python(kwargs["uri"])
                result = await session.read_resource(uri)
                return result.model_dump(mode="json")

            if operation == "list_prompts":
                result = await session.list_prompts()
                return result.model_dump(mode="json")

            if operation == "get_prompt":
                result = await session.get_prompt(
                    kwargs["name"],
                    arguments=kwargs.get("arguments"),
                )
                return result.model_dump(mode="json")

            raise ValueError(f"Unsupported MCP operation: {operation}")

    @asynccontextmanager
    async def _open_session(self, **kwargs):
        transport = kwargs.get("transport", "stdio")
        if transport == "stdio":
            parameters = StdioServerParameters(
                command=kwargs["command"],
                args=kwargs.get("args", []),
                env=kwargs.get("env"),
                cwd=kwargs.get("cwd"),
            )
            async with stdio_client(parameters) as streams:
                read_stream, write_stream = streams
                async with ClientSession(read_stream, write_stream) as session:
                    yield session
            return

        if transport == "streamable-http":
            async with streamable_http_client(kwargs["url"]) as transport_streams:
                read_stream, write_stream, _ = transport_streams
                async with ClientSession(read_stream, write_stream) as session:
                    yield session
            return

        raise ValueError(f"Unsupported MCP transport: {transport}")

    async def _execute_streamable_http(self, **kwargs) -> dict[str, Any]:
        request_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            MCP_PROTOCOL_VERSION_HEADER: LATEST_PROTOCOL_VERSION,
            **(kwargs.get("headers") or {}),
        }

        async with httpx.AsyncClient(timeout=30, trust_env=False) as client:
            session_id = await self._initialize_http_session(client, kwargs["url"], request_headers)
            if session_id:
                request_headers[MCP_SESSION_ID_HEADER] = session_id

            await client.post(
                kwargs["url"],
                json={
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {},
                },
                headers=request_headers,
            )

            method, params = self._http_operation_to_request(kwargs)
            response = await client.post(
                kwargs["url"],
                json={
                    "jsonrpc": "2.0",
                    "id": 2,
                    "method": method,
                    "params": params,
                },
                headers=request_headers,
            )
            response.raise_for_status()
            payload = response.json()
            if "error" in payload:
                raise RuntimeError(f"MCP HTTP error: {payload['error']}")
            return payload["result"]

    async def _initialize_http_session(
        self,
        client: httpx.AsyncClient,
        url: str,
        headers: dict[str, str],
    ) -> str | None:
        response = await client.post(
            url,
            json={
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": LATEST_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {
                        "name": "researchos",
                        "version": "0.0.1",
                    },
                },
            },
            headers=headers,
        )
        response.raise_for_status()
        payload = response.json()
        if "error" in payload:
            raise RuntimeError(f"MCP initialize error: {payload['error']}")
        return response.headers.get(MCP_SESSION_ID_HEADER)

    def _http_operation_to_request(self, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        operation = kwargs["operation"]
        if operation == "list_tools":
            return "tools/list", {}
        if operation == "call_tool":
            return "tools/call", {
                "name": kwargs["name"],
                "arguments": kwargs.get("arguments", {}),
            }
        if operation == "list_resources":
            return "resources/list", {}
        if operation == "read_resource":
            return "resources/read", {"uri": kwargs["uri"]}
        if operation == "list_prompts":
            return "prompts/list", {}
        if operation == "get_prompt":
            return "prompts/get", {
                "name": kwargs["name"],
                "arguments": kwargs.get("arguments", {}),
            }
        raise ValueError(f"Unsupported MCP operation: {operation}")
