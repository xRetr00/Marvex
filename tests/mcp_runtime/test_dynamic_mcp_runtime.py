from __future__ import annotations

from types import SimpleNamespace

from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from packages.capability_runtime import (
    CapabilityCallProposal,
    CapabilityExecutionMode,
    CapabilityExecutionRequest,
    CapabilityKind,
    CapabilityPermissionDecision,
    CapabilityRef,
    HumanApprovalRequirement,
    ToolRiskLevel,
    ToolSideEffectLevel,
)
from packages.mcp_runtime import (
    InstalledMcpServerConfig,
    McpServerPackageSpec,
    McpServerRuntimeRegistry,
    McpServerTransportConfig,
)


class _FakeMcpClient:
    def __init__(self) -> None:
        self.called: list[tuple[str, dict[str, object]]] = []

    async def list_tools(self, server: InstalledMcpServerConfig) -> ListToolsResult:
        assert server.server_id == "demo.server"
        return ListToolsResult(
            tools=[
                Tool(
                    name="lookup",
                    description="Look up demo data.",
                    inputSchema={
                        "type": "object",
                        "properties": {"query": {"type": "string"}},
                        "required": ["query"],
                    },
                )
            ]
        )

    async def call_tool(
        self,
        server: InstalledMcpServerConfig,
        tool_name: str,
        arguments: dict[str, object],
    ) -> CallToolResult:
        self.called.append((tool_name, arguments))
        return CallToolResult(
            content=[TextContent(type="text", text=f"found {arguments['query']}")],
            isError=False,
        )


def _request(tool_id: str, arguments: dict[str, object]) -> CapabilityExecutionRequest:
    ref = CapabilityRef(kind=CapabilityKind.MCP_TOOL, identifier=tool_id)
    proposal = CapabilityCallProposal(
        schema_version="1",
        proposal_id=f"proposal.{tool_id}",
        trace_id="trace-1",
        turn_id="turn-1",
        capability_ref=ref,
        proposed_action=tool_id,
        risk_level=ToolRiskLevel.SAFE,
        side_effect_level=ToolSideEffectLevel.READ_ONLY,
        execution_mode=CapabilityExecutionMode.PROPOSAL_ONLY,
        arguments_schema={"type": "object"},
    )
    permission = CapabilityPermissionDecision(
        schema_version="1",
        decision_id="permission-1",
        capability_ref=ref,
        decision="approved",
        reason_code="policy_allowlisted",
        human_approval=HumanApprovalRequirement(required=False, reason_code="not_required", prompt_user_visible=False),
    )
    return CapabilityExecutionRequest(
        schema_version="1",
        request_id=f"request.{tool_id}",
        trace_id="trace-1",
        turn_id="turn-1",
        proposal=proposal,
        permission_decision=permission,
        arguments=arguments,
    )


def test_dynamic_mcp_registry_discovers_tools_exposes_schema_and_executes(tmp_path):
    client = _FakeMcpClient()
    registry = McpServerRuntimeRegistry(
        state_path=tmp_path / "mcp.json",
        client=client,
    )
    server = InstalledMcpServerConfig(
        server_id="demo.server",
        display_name="Demo Server",
        source="official_registry",
        transport=McpServerTransportConfig(type="stdio", command="python", args=("demo.py",)),
        package=McpServerPackageSpec(registry_type="pypi", identifier="demo-mcp", version="1.2.3"),
        allowed_tool_names=("lookup",),
        enabled=True,
    )

    registry.upsert_server(server)
    registry.refresh_server_tools("demo.server")
    tool_registry = registry.to_tool_registry()
    schemas = tool_registry.tool_schemas()

    assert schemas[0]["function"]["name"] == "mcp.demo.server.lookup"
    assert schemas[0]["function"]["parameters"]["required"] == ["query"]

    result = tool_registry.execute(
        _request("mcp.demo.server.lookup", {"query": "alpha"})
    )

    assert result.status == "succeeded"
    assert result.safe_result["content_text_preview"] == "found alpha"
    assert client.called == [("lookup", {"query": "alpha"})]
    assert registry.safe_projection()["servers"][0]["tool_count"] == 1

