from __future__ import annotations

from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import (
    CapabilityExecutionRequest,
    CapabilityKind,
    CapabilityManifest,
    CapabilityRef,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)

from .base import Tool, succeeded_result


class McpEchoParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(default="", max_length=500)


class LocalMcpEchoTool(Tool):
    """Bounded MCP fixture exposed through the agentic tool registry."""

    id: ClassVar[str] = "mcp.local.echo"
    name: ClassVar[str] = "Local MCP Echo"
    description: ClassVar[str] = "Call the local MCP echo fixture and return its result."
    params_model: ClassVar[type[BaseModel]] = McpEchoParams
    ref_prefix: ClassVar[str] = ""
    risk_level: ClassVar[ToolRiskLevel] = ToolRiskLevel.SAFE
    side_effect_level: ClassVar[ToolSideEffectLevel] = ToolSideEffectLevel.READ_ONLY

    def capability_ref(self) -> CapabilityRef:
        return CapabilityRef(kind=CapabilityKind.MCP_TOOL, identifier=self.identifier())

    def to_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            schema_version=self.schema_version,
            capability_ref=self.capability_ref(),
            display_name=self.name,
            description=self.description,
            owner_package="packages.adapters.capabilities.tools.mcp",
            adapter_boundary="agentic_mcp_tool_fixture",
            permissions=("mcp.local.call",),
            input_schema=self.json_schema(),
            metadata={
                "server_id": "local",
                "tool_name": "echo",
                "arbitrary_server_execution_allowed": False,
                "raw_mcp_payload_persisted": False,
            },
            enabled_by_default=False,
        )

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        params = McpEchoParams.model_validate(request.arguments)
        return succeeded_result(
            request,
            {
                "server_id": "local",
                "tool_name": "echo",
                "echo": params.message,
                "allowlisted": True,
                "raw_mcp_payload_persisted": False,
            },
        )


__all__ = ["LocalMcpEchoTool", "McpEchoParams"]
