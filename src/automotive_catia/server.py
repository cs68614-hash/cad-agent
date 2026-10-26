"""One MCP protocol server; all operations share the coordinator's STA runtime."""
from __future__ import annotations

import inspect
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import CallToolResult, TextContent, Tool


def result_to_mcp(result: dict) -> CallToolResult:
    failed = result.get("ok") is False or result.get("status") in {
        "error", "failed", "unknown", "unknown_outcome", "disabled", "no_material_removed"
    }
    return CallToolResult(
        content=[TextContent(type="text", text=json.dumps(result, ensure_ascii=False, allow_nan=False))],
        structuredContent=result,
        isError=failed,
    )


def create_server(coordinator) -> Server:
    server = Server("automotive-catia-mcp")

    @server.list_tools()
    async def list_tools():
        return [Tool(**entry) for entry in coordinator.list_tools()]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict | None):
        result = await coordinator.call(name, arguments or {})
        return result_to_mcp(result)

    return server


async def close_coordinator(coordinator):
    result = coordinator.close()
    if inspect.isawaitable(result):
        await result


async def serve_stdio(coordinator):
    server = create_server(coordinator)
    try:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())
    finally:
        await close_coordinator(coordinator)
