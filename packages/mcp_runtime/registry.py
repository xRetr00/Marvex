from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from mcp.types import CallToolResult, Tool as SdkTool

from packages.adapters.capabilities.tools import ToolRegistry
from packages.adapters.capabilities.tools.base import Tool
from packages.capability_runtime import (
    CapabilityExecutionRequest,
    CapabilityKind,
    CapabilityManifest,
    CapabilityRef,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)
from packages.mcp_runtime.client import McpRuntimeClient, SdkMcpRuntimeClient, run_async
from packages.mcp_runtime.models import DiscoveredMcpTool, InstalledMcpServerConfig


class DynamicMcpTool(Tool):
    id = "dynamic"
    name = "Dynamic MCP Tool"
    description = "Call an installed and allowlisted MCP server tool."
    ref_prefix = ""
    risk_level = ToolRiskLevel.SAFE
    side_effect_level = ToolSideEffectLevel.READ_ONLY

    def __init__(
        self,
        *,
        server: InstalledMcpServerConfig,
        discovered: DiscoveredMcpTool,
        client: McpRuntimeClient,
    ) -> None:
        self._server = server
        self._discovered = discovered
        self._client = client
        self.name = f"{server.display_name}: {discovered.tool_name}"
        self.description = discovered.description or "Call an installed MCP server tool."

    def tool_id(self) -> str:
        return self._discovered.capability_id()

    def capability_ref(self) -> CapabilityRef:
        return CapabilityRef(kind=CapabilityKind.MCP_TOOL, identifier=self.tool_id())

    def json_schema(self) -> dict[str, object]:
        return dict(self._discovered.input_schema or {"type": "object"})

    def to_manifest(self) -> CapabilityManifest:
        return CapabilityManifest(
            schema_version="1",
            capability_ref=self.capability_ref(),
            display_name=self.name,
            description=self.description,
            owner_package="packages.mcp_runtime",
            adapter_boundary="mcp_sdk_dynamic_tool",
            permissions=(f"mcp.{self._server.server_id}.call",),
            input_schema=self.json_schema(),
            metadata={
                "server_id": self._server.server_id,
                "tool_name": self._discovered.tool_name,
                "transport": self._server.transport.type,
                "raw_mcp_payload_persisted": False,
            },
            enabled_by_default=False,
        )

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        if not self._server.enabled:
            return _result(request, status="denied", safe_result={"reason_code": "mcp_server_disabled"})
        if self._discovered.tool_name not in self._server.allowed_tool_names:
            return _result(request, status="denied", safe_result={"reason_code": "mcp_tool_not_allowlisted"})
        result = run_async(
            self._client.call_tool(
                self._server,
                self._discovered.tool_name,
                dict(request.arguments),
            )
        )
        return _result(
            request,
            status="failed" if result.isError else "succeeded",
            safe_result=_safe_call_result(result),
        )


class McpServerRuntimeRegistry:
    def __init__(
        self,
        *,
        state_path: str | Path,
        client: McpRuntimeClient | None = None,
    ) -> None:
        self._state_path = Path(state_path)
        self._client = client or SdkMcpRuntimeClient()
        self._servers: dict[str, InstalledMcpServerConfig] = {}
        self._tools: dict[str, tuple[DiscoveredMcpTool, ...]] = {}
        self._load()

    def upsert_server(self, server: InstalledMcpServerConfig) -> InstalledMcpServerConfig:
        self._servers[server.server_id] = server
        self._save()
        return server

    def servers(self) -> tuple[InstalledMcpServerConfig, ...]:
        return tuple(self._servers.values())

    def refresh_server_tools(self, server_id: str) -> tuple[DiscoveredMcpTool, ...]:
        server = self._servers[server_id]
        result = run_async(self._client.list_tools(server))
        tools = tuple(_from_sdk_tool(server.server_id, tool) for tool in getattr(result, "tools", ()))
        self._tools[server_id] = tools
        return tools

    def refresh_all_enabled(self) -> tuple[DiscoveredMcpTool, ...]:
        all_tools: list[DiscoveredMcpTool] = []
        for server in self._servers.values():
            if not server.enabled:
                continue
            all_tools.extend(self.refresh_server_tools(server.server_id))
        return tuple(all_tools)

    def to_tool_registry(self) -> ToolRegistry:
        tools: list[Tool] = []
        for server in self._servers.values():
            if not server.enabled:
                continue
            for discovered in self._tools.get(server.server_id, ()):
                if discovered.tool_name in server.allowed_tool_names:
                    tools.append(DynamicMcpTool(server=server, discovered=discovered, client=self._client))
        return ToolRegistry(tuple(tools))

    def safe_projection(self) -> dict[str, object]:
        return {
            "schema_version": "1",
            "servers": [
                server.safe_projection(tool_count=len(self._tools.get(server.server_id, ())))
                for server in self._servers.values()
            ],
            "server_count": len(self._servers),
            "raw_registry_payload_persisted": False,
        }

    def _load(self) -> None:
        if not self._state_path.is_file():
            return
        try:
            payload = json.loads(self._state_path.read_text(encoding="utf-8"))
            for item in payload.get("servers", []):
                server = InstalledMcpServerConfig.model_validate(item)
                self._servers[server.server_id] = server
        except Exception:
            self._servers = {}

    def _save(self) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1",
            "servers": [server.model_dump(mode="json") for server in self._servers.values()],
            "raw_registry_payload_persisted": False,
        }
        self._state_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _from_sdk_tool(server_id: str, tool: SdkTool) -> DiscoveredMcpTool:
    schema = getattr(tool, "inputSchema", None)
    return DiscoveredMcpTool(
        server_id=server_id,
        tool_name=str(tool.name),
        description=str(tool.description or "MCP tool")[:500],
        input_schema=schema if isinstance(schema, dict) else {"type": "object"},
    )


def _safe_call_result(result: CallToolResult) -> dict[str, object]:
    texts: list[str] = []
    for content in result.content:
        text = getattr(content, "text", None)
        if isinstance(text, str):
            texts.append(text)
    preview = " ".join(texts)[:800]
    return {
        "content_count": len(result.content),
        "content_types": [str(getattr(content, "type", type(content).__name__)) for content in result.content],
        "content_text_preview": preview,
        "structured_content_present": getattr(result, "structuredContent", None) is not None,
        "is_error": bool(result.isError),
        "raw_mcp_payload_persisted": False,
    }


def _result(
    request: CapabilityExecutionRequest,
    *,
    status: str,
    safe_result: dict[str, object],
) -> CapabilityResultEnvelope:
    return CapabilityResultEnvelope(
        schema_version=request.schema_version,
        result_id=f"{request.request_id}:result",
        trace_id=request.trace_id,
        turn_id=request.turn_id,
        capability_ref=request.proposal.capability_ref,
        status=status,
        safe_result=safe_result,
        raw_input_persisted=False,
        raw_output_persisted=False,
    )


__all__ = ["DynamicMcpTool", "McpServerRuntimeRegistry"]

