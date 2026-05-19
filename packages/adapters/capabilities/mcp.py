from __future__ import annotations

from collections.abc import Mapping, Sequence
from enum import Enum
from typing import Any, Literal, Protocol

from mcp import ClientSession
from mcp.types import CallToolResult, Tool
from pydantic import BaseModel, ConfigDict, Field

from packages.capability_runtime import (
    CapabilityCallProposal,
    CapabilityExecutionRequest,
    CapabilityKind,
    CapabilityManifest,
    CapabilityRef,
    CapabilityResultEnvelope,
)

_SAFE_ID_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.:-_")
_UNSAFE_KEY_PARTS = ("authorization", "bearer", "password", "prompt", "raw", "secret", "token", "transcript")
_SCHEMA_KEYS = frozenset(
    {
        "additionalProperties",
        "allOf",
        "anyOf",
        "enum",
        "format",
        "items",
        "maximum",
        "maxItems",
        "maxLength",
        "minimum",
        "minItems",
        "minLength",
        "oneOf",
        "properties",
        "required",
        "type",
    }
)

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
        server_id = _safe_identifier_part(self.server_ref.server_id)
        tool_name = _safe_identifier_part(self.tool_name)
        return CapabilityRef(kind=CapabilityKind.MCP_TOOL, identifier=f"mcp.{server_id}.{tool_name}")


class McpAllowlist(McpAdapterModel):
    allowed_server_ids: tuple[str, ...]
    allowed_tool_names: tuple[str, ...]

    def allows_server(self, server_ref: McpServerRef) -> bool:
        return server_ref.server_id in self.allowed_server_ids

    def allows(self, tool_ref: McpToolRef) -> bool:
        return self.allows_server(tool_ref.server_ref) and tool_ref.tool_name in self.allowed_tool_names


class McpAllowlistPolicy(McpAdapterModel):
    policy_id: str = Field(..., min_length=1)
    allowed_server_ids: tuple[str, ...]
    allowed_tool_names: tuple[str, ...]
    policy_source: Literal["runtime_config", "control_plane", "test_fixture"]
    raw_config_persisted: Literal[False] = False

    @classmethod
    def from_runtime_config(
        cls,
        *,
        policy_id: str,
        allowed_server_ids: tuple[str, ...],
        allowed_tool_names: tuple[str, ...],
        source: Literal["runtime_config", "control_plane", "test_fixture"] = "runtime_config",
    ) -> "McpAllowlistPolicy":
        return cls(policy_id=policy_id, allowed_server_ids=allowed_server_ids, allowed_tool_names=allowed_tool_names, policy_source=source)

    def to_allowlist(self) -> McpAllowlist:
        return McpAllowlist(allowed_server_ids=self.allowed_server_ids, allowed_tool_names=self.allowed_tool_names)

    def safe_projection(self) -> dict[str, object]:
        return {
            "policy_id": self.policy_id,
            "policy_source": self.policy_source,
            "allowed_server_count": len(self.allowed_server_ids),
            "allowed_tool_count": len(self.allowed_tool_names),
            "raw_config_persisted": False,
        }


class McpAllowlistProposal(McpAdapterModel):
    proposal_id: str
    policy_id: str
    server_id: str
    tool_name: str
    requested_by: Literal["control_plane", "runtime_config", "test_fixture"]
    action: Literal["add_tool", "remove_tool"]
    review_required: Literal[True] = True
    applied_without_review: Literal[False] = False

    @classmethod
    def propose_add_tool(
        cls,
        *,
        policy_id: str,
        server_id: str,
        tool_name: str,
        requested_by: Literal["control_plane", "runtime_config", "test_fixture"],
    ) -> "McpAllowlistProposal":
        return cls(proposal_id=f"mcp.allowlist.{_safe_identifier_part(server_id)}.{_safe_identifier_part(tool_name)}", policy_id=policy_id, server_id=server_id, tool_name=tool_name, requested_by=requested_by, action="add_tool")

    def safe_projection(self) -> dict[str, object]:
        return {
            "proposal_id": self.proposal_id,
            "policy_id": self.policy_id,
            "server_id": self.server_id,
            "tool_name": self.tool_name,
            "requested_by": self.requested_by,
            "action": self.action,
            "review_required": True,
            "applied_without_review": False,
        }


class McpToolListingProjection(McpAdapterModel):
    tool_ref: McpToolRef
    capability_ref: CapabilityRef
    allowed: bool
    blocked_reason_code: Literal["not_allowlisted", "blocked_dangerous_tool_name"] | None = None
    capability_manifest: CapabilityManifest | None = None
    raw_schema_persisted: Literal[False] = False

    @classmethod
    def from_tool_ref(cls, tool_ref: McpToolRef, *, allowlist: McpAllowlist) -> McpToolListingProjection:
        allowed, blocked_reason_code = _classify_tool(tool_ref, allowlist=allowlist)
        manifest = _manifest_for_tool(tool_ref, "MCP tool", {"type": "object"}) if allowed else None
        return cls(
            tool_ref=tool_ref,
            capability_ref=tool_ref.capability_ref(),
            allowed=allowed,
            blocked_reason_code=blocked_reason_code,
            capability_manifest=manifest,
        )

    @classmethod
    def from_sdk_tool(
        cls,
        server_ref: McpServerRef,
        tool: Tool,
        *,
        allowlist: McpAllowlist,
    ) -> McpToolListingProjection:
        tool_ref = McpToolRef(server_ref=server_ref, tool_name=tool.name)
        allowed, blocked_reason_code = _classify_tool(tool_ref, allowlist=allowlist)
        safe_schema = _sanitize_schema(tool.inputSchema) if allowed else None
        manifest = _manifest_for_tool(tool_ref, tool.description or "MCP tool", safe_schema) if allowed else None
        return cls(
            tool_ref=tool_ref,
            capability_ref=tool_ref.capability_ref(),
            allowed=allowed,
            blocked_reason_code=blocked_reason_code,
            capability_manifest=manifest,
        )

    def safe_projection(self) -> dict[str, object]:
        return {
            "capability_ref": self.capability_ref.safe_projection(),
            "server_id": self.tool_ref.server_ref.server_id,
            "transport": self.tool_ref.server_ref.transport.value,
            "tool_name": self.tool_ref.tool_name,
            "allowed": self.allowed,
            "blocked_reason_code": self.blocked_reason_code,
            "input_schema_present": self.capability_manifest is not None and self.capability_manifest.input_schema is not None,
            "raw_schema_persisted": False,
        }


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
        if not listing.allowed:
            raise ValueError("blocked MCP tools cannot create call proposals")
        arguments_schema = listing.capability_manifest.input_schema if listing.capability_manifest else {"type": "object"}
        return cls(
            schema_version="1",
            proposal_id=proposal_id,
            trace_id=trace_id,
            turn_id=turn_id,
            capability_ref=listing.capability_ref,
            proposed_action=listing.tool_ref.tool_name,
            risk_level="medium",
            arguments_schema=arguments_schema or {"type": "object"},
            raw_arguments_persisted=False,
        )


class McpPermissionGatedCallRequest(McpAdapterModel):
    proposal: McpToolCallProposal
    marvex_policy_approved: bool
    auto_call_allowed: Literal[False] = False


class McpClientSession(Protocol):
    async def initialize(self) -> object: ...

    async def list_tools(self) -> object: ...

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> CallToolResult: ...


class McpSdkAdapter:
    def __init__(self, *, session: ClientSession | McpClientSession, allowlist: McpAllowlist) -> None:
        self._session = session
        self._allowlist = allowlist

    async def discover_tools(self, server_ref: McpServerRef) -> tuple[McpToolListingProjection, ...]:
        if not self._allowlist.allows_server(server_ref):
            return ()
        await self._session.initialize()
        result = await self._session.list_tools()
        tools = tuple(getattr(result, "tools", ()))
        return tuple(McpToolListingProjection.from_sdk_tool(server_ref, tool, allowlist=self._allowlist) for tool in tools)

    def create_call_proposal(
        self,
        listing: McpToolListingProjection,
        *,
        proposal_id: str,
        trace_id: str,
        turn_id: str,
    ) -> McpToolCallProposal:
        return McpToolCallProposal.from_listing(
            listing,
            proposal_id=proposal_id,
            trace_id=trace_id,
            turn_id=turn_id,
        )

    async def call_approved_tool(
        self,
        server_ref: McpServerRef,
        execution_request: CapabilityExecutionRequest,
    ) -> CapabilityResultEnvelope:
        tool_ref = McpToolRef(server_ref=server_ref, tool_name=execution_request.proposal.proposed_action)
        if _dangerous_tool_name(tool_ref.tool_name):
            return _result_envelope(execution_request, status="denied", safe_result={"reason_code": "blocked_dangerous_tool_name"})
        if not self._allowlist.allows(tool_ref) or tool_ref.capability_ref() != execution_request.proposal.capability_ref:
            return _result_envelope(execution_request, status="denied", safe_result={"reason_code": "not_allowlisted"})
        result = await self._session.call_tool(execution_request.proposal.proposed_action, arguments=execution_request.arguments)
        return _result_envelope(
            execution_request,
            status="failed" if result.isError else "succeeded",
            safe_result=_safe_call_result(result),
        )


class DisabledMcpBackend:
    def list_tools(self, server_ref: McpServerRef) -> tuple[McpToolListingProjection, ...]:
        raise RuntimeError("MCP backend is disabled until official SDK adoption is approved")


def _classify_tool(
    tool_ref: McpToolRef,
    *,
    allowlist: McpAllowlist,
) -> tuple[bool, Literal["not_allowlisted", "blocked_dangerous_tool_name"] | None]:
    if _dangerous_tool_name(tool_ref.tool_name):
        return False, "blocked_dangerous_tool_name"
    if not allowlist.allows(tool_ref):
        return False, "not_allowlisted"
    return True, None


def _manifest_for_tool(tool_ref: McpToolRef, description: str, input_schema: dict[str, Any] | None) -> CapabilityManifest:
    return CapabilityManifest(
        schema_version="1",
        capability_ref=tool_ref.capability_ref(),
        display_name=tool_ref.tool_name,
        description=description,
        owner_package="packages.adapters.capabilities.mcp",
        adapter_boundary="mcp_protocol_adapter_only",
        permissions=(f"mcp.{_safe_identifier_part(tool_ref.server_ref.server_id)}.call",),
        input_schema=input_schema,
        metadata={
            "server_id": tool_ref.server_ref.server_id,
            "transport": tool_ref.server_ref.transport.value,
            "origin": tool_ref.server_ref.origin,
            "arbitrary_server_execution_allowed": False,
        },
        enabled_by_default=False,
    )


def _sanitize_schema(schema: Mapping[str, Any] | None) -> dict[str, Any]:
    if not isinstance(schema, Mapping):
        return {"type": "object"}
    sanitized = _sanitize_schema_mapping(schema)
    return sanitized if sanitized else {"type": "object"}


def _sanitize_schema_mapping(schema: Mapping[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    allowed_properties: set[str] = set()
    for key, value in schema.items():
        if key not in _SCHEMA_KEYS or _unsafe_key(key):
            continue
        if key == "properties" and isinstance(value, Mapping):
            properties: dict[str, Any] = {}
            for property_name, property_schema in value.items():
                if _unsafe_key(str(property_name)) or not _safe_schema_property_name(str(property_name)):
                    continue
                properties[str(property_name)] = _sanitize_schema_value(property_schema)
                allowed_properties.add(str(property_name))
            if properties:
                sanitized[key] = properties
            continue
        if key == "required" and isinstance(value, Sequence) and not isinstance(value, str):
            required = [str(item) for item in value if str(item) in allowed_properties and not _unsafe_key(str(item))]
            if required:
                sanitized[key] = required
            continue
        sanitized[key] = _sanitize_schema_value(value)
    return sanitized


def _sanitize_schema_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return _sanitize_schema_mapping(value)
    if isinstance(value, list):
        return [_sanitize_schema_value(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return str(type(value).__name__)


def _safe_call_result(result: CallToolResult) -> dict[str, Any]:
    content_types = [str(getattr(content, "type", type(content).__name__)) for content in result.content]
    return {
        "content_count": len(result.content),
        "content_types": content_types,
        "is_error": bool(result.isError),
        "structured_content_present": result.structuredContent is not None,
    }


def _result_envelope(
    execution_request: CapabilityExecutionRequest,
    *,
    status: Literal["succeeded", "failed", "denied"],
    safe_result: dict[str, Any],
) -> CapabilityResultEnvelope:
    return CapabilityResultEnvelope(
        schema_version=execution_request.schema_version,
        result_id=f"result-{execution_request.request_id}",
        trace_id=execution_request.trace_id,
        turn_id=execution_request.turn_id,
        capability_ref=execution_request.proposal.capability_ref,
        status=status,
        safe_result=safe_result,
        raw_input_persisted=False,
        raw_output_persisted=False,
    )


def _dangerous_tool_name(value: str) -> bool:
    lowered = value.lower()
    normalized = "".join(character for character in lowered if character.isalnum())
    tokens = tuple("".join(character if character.isalnum() else " " for character in lowered).split())
    exact_parts = {"bash", "browser", "command", "desktop", "fetch", "file", "fs", "http", "network", "shell", "terminal", "url"}
    compact_parts = {"filesystem", "powershell", "webbrowser"}
    return (
        any(token in exact_parts for token in tokens)
        or any(part in normalized for part in compact_parts)
        or normalized.startswith("file")
        or normalized.endswith("file")
    )


def _unsafe_key(value: str) -> bool:
    normalized = "".join(character for character in value.lower() if character.isalnum())
    return any(part in normalized for part in _UNSAFE_KEY_PARTS)


def _safe_schema_property_name(value: str) -> bool:
    return bool(value) and all(character in _SAFE_ID_CHARS for character in value)


def _safe_identifier_part(value: str) -> str:
    safe = "".join(character if character in _SAFE_ID_CHARS else "-" for character in value.strip())
    safe = safe.strip(".-:_")
    return safe or "unnamed"
