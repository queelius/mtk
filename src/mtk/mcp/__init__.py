"""MCP server for mtk — exposes email archive as Claude Code tools."""

from __future__ import annotations

import asyncio


def run_server() -> None:
    """Run the MCP server on stdio transport."""
    from mcp.server.stdio import stdio_server

    from mtk.mcp.server import create_server

    server = create_server()

    async def _run() -> None:
        async with stdio_server() as (read_stream, write_stream):
            await server.run(
                read_stream,
                write_stream,
                server.create_initialization_options(),
            )

    asyncio.run(_run())
