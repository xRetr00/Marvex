from __future__ import annotations

import asyncio

from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from packages.adapters.capabilities.mcp import (
    McpAllowlist,
    McpServerRef,
    McpSdkAdapter,
    McpToolRef,
    McpTransport,
)
from packages.capability_runtime import (
    CapabilityCallProposal,
    CapabilityExecutionRequest,
    CapabilityPermissionDecision,
    HumanApprovalRequirement,
)


class FakeMcpSession:
    def __init__(self, tools: tuple[Tool, ...]) -> None:
        self.tools = tools
        self.initialized = 0
        self.called: list[tuple[str, dict[str, object]]] = []

    async def initialize(self) -> None:
        self.initialized += 1

    async def list_tools(self) -> ListToolsResult:
        return ListToolsResult(tools=list(self.tools))

    async def call_tool(self, name: str, arguments: dict[str, object]) -> CallToolResult:
        self.called.append((name, arguments))
        return CallToolResult(content=[TextContent(type="text", text="raw mcp output")], isError=False)


def test_sdk_adapter_lists_allowlisted_tools_as_safe_capability_manifests() -> None:
    async def run() -> None:
        server = McpServerRef(server_id="weather", transport=McpTransport.STREAMABLE_HTTP, origin="local_config")
        allowlist = McpAllowlist(
            allowed_server_ids=("weather",),
            allowed_tool_names=("current_weather", "run_shell"),
        )
        session = FakeMcpSession(
            tools=(
                Tool(
                    name="current_weather",
                    description="Read current weather.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "city": {"type": "string", "description": "City name"},
                            "authorizationToken": {"type": "string"},
                        },
                        "required": ["city"],
                    },
                ),
                Tool(name="run_shell", description="Dangerous local shell", inputSchema={"type": "object"}),
            )
        )

        listings = await McpSdkAdapter(session=session, allowlist=allowlist).discover_tools(server)

        assert session.initialized == 1
        assert len(listings) == 2
        allowed, blocked = listings
        assert allowed.allowed is True
        assert allowed.blocked_reason_code is None
        assert allowed.capability_manifest is not None
        assert allowed.capability_manifest.capability_ref.identifier == "mcp.weather.current_weather"
        assert allowed.capability_manifest.input_schema == {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        }
        assert allowed.raw_schema_persisted is False

        assert blocked.allowed is False
        assert blocked.blocked_reason_code == "blocked_dangerous_tool_name"
        assert blocked.capability_manifest is None
        assert blocked.safe_projection()["input_schema_present"] is False

    asyncio.run(run())


def test_sdk_adapter_calls_tools_only_from_approved_capability_execution_request() -> None:
    async def run() -> None:
        server = McpServerRef(server_id="weather", transport=McpTransport.STREAMABLE_HTTP, origin="local_config")
        allowlist = McpAllowlist(allowed_server_ids=("weather",), allowed_tool_names=("current_weather",))
        session = FakeMcpSession(
            tools=(Tool(name="current_weather", description="Read current weather.", inputSchema={"type": "object"}),)
        )
        adapter = McpSdkAdapter(session=session, allowlist=allowlist)
        listing = (await adapter.discover_tools(server))[0]
        proposal = adapter.create_call_proposal(
            listing,
            proposal_id="proposal-1",
            trace_id="trace-1",
            turn_id="turn-1",
        )
        decision = CapabilityPermissionDecision(
            schema_version="1",
            decision_id="decision-1",
            capability_ref=proposal.capability_ref,
            decision="approved",
            reason_code="allowlisted",
            human_approval=HumanApprovalRequirement(required=False, reason_code="not_required", prompt_user_visible=False),
        )
        execution_request = CapabilityExecutionRequest(
            schema_version="1",
            request_id="request-1",
            trace_id="trace-1",
            turn_id="turn-1",
            proposal=proposal,
            permission_decision=decision,
            arguments={"city": "Paris"},
        )

        result = await adapter.call_approved_tool(server, execution_request)

        assert session.called == [("current_weather", {"city": "Paris"})]
        assert result.status == "succeeded"
        assert result.raw_input_persisted is False
        assert result.raw_output_persisted is False
        assert result.safe_result == {
            "content_count": 1,
            "content_types": ["text"],
            "is_error": False,
            "structured_content_present": False,
        }

    asyncio.run(run())


def test_sdk_adapter_refuses_blocked_listing_before_tool_call() -> None:
    async def run() -> None:
        server = McpServerRef(server_id="weather", transport=McpTransport.STREAMABLE_HTTP, origin="local_config")
        allowlist = McpAllowlist(allowed_server_ids=("weather",), allowed_tool_names=())
        session = FakeMcpSession(
            tools=(Tool(name="current_weather", description="Read current weather.", inputSchema={"type": "object"}),)
        )

        listing = (await McpSdkAdapter(session=session, allowlist=allowlist).discover_tools(server))[0]

        assert listing.allowed is False
        assert listing.blocked_reason_code == "not_allowlisted"
        assert listing.capability_manifest is None

    asyncio.run(run())


def test_sdk_adapter_denies_dangerous_allowlisted_execution_request() -> None:
    async def run() -> None:
        server = McpServerRef(server_id="weather", transport=McpTransport.STREAMABLE_HTTP, origin="local_config")
        tool_ref = McpToolRef(server_ref=server, tool_name="run_shell")
        allowlist = McpAllowlist(allowed_server_ids=("weather",), allowed_tool_names=("run_shell",))
        session = FakeMcpSession(tools=())
        proposal = CapabilityCallProposal(
            schema_version="1",
            proposal_id="proposal-shell",
            trace_id="trace-1",
            turn_id="turn-1",
            capability_ref=tool_ref.capability_ref(),
            proposed_action="run_shell",
            risk_level="high",
            arguments_schema={"type": "object"},
        )
        decision = CapabilityPermissionDecision(
            schema_version="1",
            decision_id="decision-shell",
            capability_ref=proposal.capability_ref,
            decision="approved",
            reason_code="allowlisted",
            human_approval=HumanApprovalRequirement(required=False, reason_code="not_required", prompt_user_visible=False),
        )
        execution_request = CapabilityExecutionRequest(
            schema_version="1",
            request_id="request-shell",
            trace_id="trace-1",
            turn_id="turn-1",
            proposal=proposal,
            permission_decision=decision,
            arguments={"command": "echo unsafe"},
        )

        result = await McpSdkAdapter(session=session, allowlist=allowlist).call_approved_tool(server, execution_request)

        assert session.called == []
        assert result.status == "denied"
        assert result.safe_result == {"reason_code": "blocked_dangerous_tool_name"}

    asyncio.run(run())
