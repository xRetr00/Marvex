from __future__ import annotations

from typing import Any, Literal

from pydantic import Field

from packages.capability_runtime.autonomy import AutonomyPolicy
from packages.capability_runtime.models import CapabilityRuntimeModel, ToolRiskLevel


class ToolRegistryEntry(CapabilityRuntimeModel):
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    input_schema: dict[str, Any]
    risk: ToolRiskLevel
    approval_requirement: Literal["none", "policy", "human"] = "policy"
    intent_tags: tuple[str, ...]
    available: bool = True
    mcp_server_id: str | None = None


class ToolSelectionRequest(CapabilityRuntimeModel):
    intent_kind: str
    autonomy_policy: AutonomyPolicy
    route_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    mcp_allowlist: tuple[str, ...] = ()
    previous_tool_failures: tuple[str, ...] = ()


class ToolSelectionExclusion(CapabilityRuntimeModel):
    name: str
    reason_code: str


class ToolSelectionResult(CapabilityRuntimeModel):
    eligible_tools: tuple[ToolRegistryEntry, ...]
    excluded_tools: tuple[ToolSelectionExclusion, ...]
    provider_tool_schemas: tuple[dict[str, Any], ...]
    all_tools_injected: Literal[False] = False


def select_tools_for_request(request: ToolSelectionRequest, registry: tuple[ToolRegistryEntry, ...]) -> ToolSelectionResult:
    eligible: list[ToolRegistryEntry] = []
    excluded: list[ToolSelectionExclusion] = []
    for entry in registry:
        reason = _exclusion_reason(request, entry)
        if reason is None:
            eligible.append(entry)
        else:
            excluded.append(ToolSelectionExclusion(name=entry.name, reason_code=reason))
    excluded_sorted = sorted(excluded, key=lambda item: _exclusion_priority(item.reason_code))
    return ToolSelectionResult(
        eligible_tools=tuple(eligible),
        excluded_tools=tuple(excluded_sorted),
        provider_tool_schemas=tuple(_provider_schema(entry, request) for entry in eligible),
    )


def _exclusion_reason(request: ToolSelectionRequest, entry: ToolRegistryEntry) -> str | None:
    if not entry.available:
        return "tool.unavailable"
    if entry.name in request.previous_tool_failures:
        return "tool.previous_failure"
    if entry.mcp_server_id is not None and entry.mcp_server_id not in request.mcp_allowlist:
        return "tool.mcp_not_allowlisted"
    if _intent_value(request.intent_kind) not in entry.intent_tags:
        return "tool.intent_mismatch"
    if request.route_confidence < 0.35:
        return "tool.route_confidence_too_low"
    return None



def _intent_value(intent_kind: object) -> str:
    return str(getattr(intent_kind, "value", intent_kind))
def _provider_schema(entry: ToolRegistryEntry, request: ToolSelectionRequest) -> dict[str, Any]:
    return {
        "name": entry.name,
        "description": entry.description,
        "input_schema": entry.input_schema,
        "risk": entry.risk.value,
        "approval_requirement": entry.approval_requirement,
        "availability": "available" if entry.available else "unavailable",
        "autonomy_mode": request.autonomy_policy.mode.value,
    }


def _exclusion_priority(reason_code: str) -> int:
    if reason_code == "tool.previous_failure":
        return 0
    if reason_code == "tool.mcp_not_allowlisted":
        return 1
    return 2