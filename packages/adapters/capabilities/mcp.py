from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import CapabilityCallProposal, CapabilityKind, CapabilityRef


class McpAdapterModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class McpTransport(str, Enum):
    STDIO = "stdio"
    SSE = "sse"
    STREAMABLE_HTTP = "streamable_http"


class McpServerRef(McpAdapterModel):
    server_id: str = Field(..., min_length=1)
    transport: McpTransport
    origin: Literal["local_config", "official_registry_reference", "manual_test_fixture"]
    arbitrary_server_execution_allowed: Literal[False] = False


class McpToolRef(McpAdapterModel):
    server_ref: McpServerRef
    tool_name: str = Field(..., min_length=1)

    def capability_ref(self) -> CapabilityRef:
        return CapabilityRef(kind=CapabilityKind.MCP_TOOL, identifier=f"mcp.{self.server_ref.server_id}.{self.tool_name}")


class McpAllowlist(McpAdapterModel):
    allowed_server_ids: tuple[str, ...]
    allowed_tool_names: tuple[str, ...]

    def allows(self, tool_ref: McpToolRef) -> bool:
        return tool_ref.server_ref.server_id in self.allowed_server_ids and tool_ref.tool_name in self.allowed_tool_names


class McpToolListingProjection(McpAdapterModel):
    tool_ref: McpToolRef
    capability_ref: CapabilityRef
    allowed: bool
    raw_schema_persisted: Literal[False] = False

    @classmethod
    def from_tool_ref(cls, tool_ref: McpToolRef, *, allowlist: McpAllowlist) -> McpToolListingProjection:
        return cls(tool_ref=tool_ref, capability_ref=tool_ref.capability_ref(), allowed=allowlist.allows(tool_ref))


class McpToolCallProposal(CapabilityCallProposal):
    @classmethod
    def from_listing(
        cls,
        listing: McpToolListingProjection,
        *,
        proposal_id: str,
        trace_id: str,
        turn_id: str,
    ) -> McpToolCallProposal:
        return cls(
            schema_version="1",
            proposal_id=proposal_id,
            trace_id=trace_id,
            turn_id=turn_id,
            capability_ref=listing.capability_ref,
            proposed_action=listing.tool_ref.tool_name,
            risk_level="medium",
            arguments_schema={"type": "object"},
            raw_arguments_persisted=False,
        )


class McpPermissionGatedCallRequest(McpAdapterModel):
    proposal: McpToolCallProposal
    marvex_policy_approved: bool
    auto_call_allowed: Literal[False] = False


class DisabledMcpBackend:
    def list_tools(self, server_ref: McpServerRef) -> tuple[McpToolListingProjection, ...]:
        raise RuntimeError("MCP backend is disabled until official SDK adoption is approved")
