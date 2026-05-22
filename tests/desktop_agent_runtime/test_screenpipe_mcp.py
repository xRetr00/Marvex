from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from packages.adapters.capabilities.mcp import McpAllowlist, McpServerRef, McpTransport

_MODULE_PATH = Path(__file__).resolve().parents[2] / "packages" / "desktop_agent_runtime" / "screenpipe_mcp.py"
_SPEC = importlib.util.spec_from_file_location("test_screenpipe_mcp_module", _MODULE_PATH)
assert _SPEC is not None and _SPEC.loader is not None
_MODULE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MODULE)
recall_screenpipe_via_mcp = _MODULE.recall_screenpipe_via_mcp


class FakeMcpSession:
    def __init__(self, *, tools: tuple[Tool, ...], call_result: CallToolResult | None = None) -> None:
        self._tools = tools
        self._call_result = call_result or CallToolResult(content=[TextContent(type="text", text="hidden raw recall payload")], isError=False)
        self.initialized = 0
        self.called: list[tuple[str, dict[str, object]]] = []

    async def initialize(self) -> None:
        self.initialized += 1

    async def list_tools(self) -> ListToolsResult:
        return ListToolsResult(tools=list(self._tools))

    async def call_tool(self, name: str, arguments: dict[str, object]) -> CallToolResult:
        self.called.append((name, arguments))
        return self._call_result


def test_recall_screenpipe_via_mcp_returns_bounded_safe_projection_for_allowlisted_tool() -> None:
    async def run() -> None:
        session = FakeMcpSession(
            tools=(Tool(name="screenpipe_recall", description="Bounded recall", inputSchema={"type": "object"}),)
        )
        server_ref = McpServerRef(server_id="screenpipe-local", transport=McpTransport.STDIO, origin="manual_test_fixture")
        allowlist = McpAllowlist(allowed_server_ids=("screenpipe-local",), allowed_tool_names=("screenpipe_recall",))

        projection = await recall_screenpipe_via_mcp(
            session=session,
            server_ref=server_ref,
            allowlist=allowlist,
            query="find latest UI intent decisions",
            limit=99,
        )

        assert session.initialized == 1
        assert session.called == [("screenpipe_recall", {"query": "find latest UI intent decisions", "limit": 20})]
        assert projection.status == "succeeded"
        assert projection.server_id == "screenpipe-local"
        assert projection.transport == "stdio"
        assert projection.tool_name == "screenpipe_recall"
        assert projection.requested_limit == 99
        assert projection.bounded_limit == 20
        assert projection.result_content_count == 1
        assert projection.raw_screen_persisted is False
        assert projection.raw_audio_persisted is False
        assert projection.raw_transcript_persisted is False
        assert projection.raw_mcp_payload_persisted is False
        assert "hidden raw recall payload" not in projection.model_dump_json().lower()

    asyncio.run(run())


def test_recall_screenpipe_via_mcp_returns_not_available_when_no_allowed_tools() -> None:
    async def run() -> None:
        session = FakeMcpSession(tools=(Tool(name="screenpipe_recall", description="Bounded recall", inputSchema={"type": "object"}),))
        server_ref = McpServerRef(server_id="screenpipe-local", transport=McpTransport.STDIO, origin="manual_test_fixture")
        allowlist = McpAllowlist(allowed_server_ids=("screenpipe-local",), allowed_tool_names=())

        projection = await recall_screenpipe_via_mcp(
            session=session,
            server_ref=server_ref,
            allowlist=allowlist,
            query="find yesterday snippets",
            limit=5,
        )

        assert projection.status == "not_available"
        assert projection.reason_code == "no_allowlisted_recall_tool"
        assert projection.tool_name is None
        assert session.called == []
        assert projection.raw_mcp_payload_persisted is False

    asyncio.run(run())
