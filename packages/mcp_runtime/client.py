from __future__ import annotations

import asyncio
from typing import Any, Protocol

from mcp.types import CallToolResult, ListToolsResult

from packages.mcp_runtime.models import InstalledMcpServerConfig


class McpRuntimeClient(Protocol):
    async def list_tools(self, server: InstalledMcpServerConfig) -> ListToolsResult: ...

    async def call_tool(
        self,
        server: InstalledMcpServerConfig,
        tool_name: str,
        arguments: dict[str, object],
    ) -> CallToolResult: ...


class SdkMcpRuntimeClient:
    async def list_tools(self, server: InstalledMcpServerConfig) -> ListToolsResult:
        async with _session_for(server) as session:
            await session.initialize()
            return await session.list_tools()

    async def call_tool(
        self,
        server: InstalledMcpServerConfig,
        tool_name: str,
        arguments: dict[str, object],
    ) -> CallToolResult:
        async with _session_for(server) as session:
            await session.initialize()
            return await session.call_tool(tool_name, arguments)


class _session_for:
    def __init__(self, server: InstalledMcpServerConfig) -> None:
        self._server = server
        self._transport_cm: Any = None
        self._session_cm: Any = None
        self._session: Any = None

    async def __aenter__(self) -> Any:
        from mcp import ClientSession, StdioServerParameters

        transport = self._server.transport
        if transport.type == "stdio":
            from mcp.client.stdio import stdio_client

            if not transport.command:
                raise ValueError("stdio MCP transport requires command")
            params = StdioServerParameters(
                command=transport.command,
                args=list(transport.args),
                env=dict(transport.env) or None,
            )
            self._transport_cm = stdio_client(params)
            read, write = await self._transport_cm.__aenter__()
        elif transport.type == "streamable_http":
            from mcp.client.streamable_http import streamable_http_client

            if not transport.url:
                raise ValueError("streamable_http MCP transport requires url")
            self._transport_cm = streamable_http_client(transport.url)
            read, write, _ = await self._transport_cm.__aenter__()
        elif transport.type == "sse":
            from mcp.client.sse import sse_client

            if not transport.url:
                raise ValueError("sse MCP transport requires url")
            self._transport_cm = sse_client(transport.url)
            read, write = await self._transport_cm.__aenter__()
        else:
            raise ValueError("unsupported MCP transport")
        self._session_cm = ClientSession(read, write)
        self._session = await self._session_cm.__aenter__()
        return self._session

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._session_cm is not None:
            await self._session_cm.__aexit__(exc_type, exc, tb)
        if self._transport_cm is not None:
            await self._transport_cm.__aexit__(exc_type, exc, tb)


def run_async(coro: Any) -> Any:
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    raise RuntimeError("MCP runtime cannot run blocking SDK calls inside an active event loop")


__all__ = ["McpRuntimeClient", "SdkMcpRuntimeClient", "run_async"]

