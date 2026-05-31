from __future__ import annotations

import asyncio
import os
from typing import Literal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from packages.automation_runtime import persist_automation_artifacts
from packages.capability_runtime import (
    CapabilityExecutionMode,
    CapabilityKind,
    CapabilityRef,
    CapabilityResultEnvelope,
    ToolRiskLevel,
    ToolSideEffectLevel,
)


class ComputerUseModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class WindowsMcpServerConfig(ComputerUseModel):
    server_id: str = "windows-mcp"
    command: str = "uvx"
    args: tuple[str, ...] = ("windows-mcp", "serve", "--transport", "stdio")
    transport: Literal["stdio"] = "stdio"
    local_only: Literal[True] = True
    destructive_tools: tuple[str, ...] = ("PowerShell", "Registry", "Delete", "Shutdown", "Restart")

    @classmethod
    def builtin(cls) -> "WindowsMcpServerConfig":
        return cls()


class ComputerUseExecutionReport(ComputerUseModel):
    status: Literal["succeeded", "failed", "denied"] = "succeeded"
    backend: str = "windows-mcp"
    tool_name: str | None = None
    action_count: int = Field(default=0, ge=0)
    reason_code: str | None = None
    artifact_payloads: dict[str, Any] = Field(default_factory=dict)


class ComputerUseHarnessConfig(ComputerUseModel):
    schema_version: str = Field(..., min_length=1)
    adapter_id: str = Field(..., min_length=1)
    backend: str = Field(..., min_length=1)
    isolated_environment_required: Literal[True] = True
    screen_content_untrusted: Literal[True] = True
    credential_entry_allowed: Literal[False] = False
    arbitrary_desktop_control_allowed: Literal[False] = False
    raw_screen_persisted: Literal[False] = False

    @classmethod
    def from_openai(cls, config) -> ComputerUseHarnessConfig:
        return cls(
            schema_version=config.schema_version,
            adapter_id=config.adapter_id,
            backend="openai_computer_use",
            isolated_environment_required=config.isolated_environment_required,
            screen_content_untrusted=config.screen_content_untrusted,
        )


class ComputerUseTaskProposal(ComputerUseModel):
    schema_version: str = Field(..., min_length=1)
    proposal_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    task_summary: str = Field(..., min_length=1, max_length=500)
    harness_config: ComputerUseHarnessConfig


class ComputerUseActionProposal(ComputerUseModel):
    schema_version: str = Field(..., min_length=1)
    action_id: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    task_proposal_id: str = Field(..., min_length=1)
    action_summary: str = Field(..., min_length=1, max_length=500)
    harness_config: ComputerUseHarnessConfig
    risk_level: ToolRiskLevel = ToolRiskLevel.HIGH
    side_effect_level: ToolSideEffectLevel = ToolSideEffectLevel.DESKTOP_ACTION
    requires_approval: Literal[True] = True

    @classmethod
    def from_task(
        cls,
        task: ComputerUseTaskProposal,
        *,
        action_id: str,
        action_summary: str,
    ) -> ComputerUseActionProposal:
        return cls(
            schema_version=task.schema_version,
            action_id=action_id,
            trace_id=task.trace_id,
            turn_id=task.turn_id,
            task_proposal_id=task.proposal_id,
            action_summary=action_summary,
            harness_config=task.harness_config,
        )

    def to_capability_proposal(self):
        from packages.capability_runtime import CapabilityCallProposal

        return CapabilityCallProposal(
            schema_version=self.schema_version,
            proposal_id=self.action_id,
            trace_id=self.trace_id,
            turn_id=self.turn_id,
            capability_ref=CapabilityRef(kind=CapabilityKind.TOOL, identifier="computer_use.action"),
            proposed_action="computer_use_action",
            risk_level=self.risk_level,
            side_effect_level=self.side_effect_level,
            execution_mode=CapabilityExecutionMode.REQUIRES_APPROVAL,
            arguments_schema={"type": "object"},
            raw_arguments_persisted=False,
        )


class ComputerUseResultEnvelope(ComputerUseModel):
    result: CapabilityResultEnvelope
    raw_screen_persisted: Literal[False] = False
    raw_action_payload_persisted: Literal[False] = False

    @classmethod
    def from_proposal(
        cls,
        proposal: ComputerUseActionProposal,
        *,
        result_id: str,
        status: Literal["succeeded", "failed", "denied", "requires_human_approval"],
        safe_result: dict[str, object],
    ) -> ComputerUseResultEnvelope:
        return cls(
            result=CapabilityResultEnvelope(
                schema_version=proposal.schema_version,
                result_id=result_id,
                trace_id=proposal.trace_id,
                turn_id=proposal.turn_id,
                capability_ref=proposal.to_capability_proposal().capability_ref,
                status=status,
                safe_result=safe_result,
                raw_input_persisted=False,
                raw_output_persisted=False,
            )
        )


def destructive_action_requested(arguments: dict[str, object], *, action: str = "") -> bool:
    text = " ".join(
        str(value)
        for value in (
            action,
            arguments.get("action_kind"),
            arguments.get("task"),
            arguments.get("command"),
            arguments.get("tool_name"),
        )
        if value
    ).lower()
    destructive = (
        "delete",
        "remove file",
        "shutdown",
        "shut down",
        "restart",
        "reboot",
        "format",
        "registry",
        "regedit",
        "powershell",
        "power shell",
    )
    return any(part in text for part in destructive)


def destructive_action_approved(arguments: dict[str, object]) -> bool:
    return str(arguments.get("destructive_action_decision") or "").strip().lower() == "approve"


def execute_windows_computer_action(request) -> ComputerUseExecutionReport:
    if os.name != "nt":
        return ComputerUseExecutionReport(status="failed", reason_code="windows_required")
    if not _live_execution_enabled(request.arguments):
        return ComputerUseExecutionReport(status="failed", reason_code="windows_mcp_live_execution_not_enabled")
    try:
        return asyncio.run(_execute_windows_mcp(request.arguments))
    except Exception as exc:  # pragma: no cover - live MCP availability varies by machine
        return ComputerUseExecutionReport(
            status="failed",
            reason_code=f"windows_mcp_execution_failed:{type(exc).__name__}",
            artifact_payloads={"error": repr(exc)} if _raw_persistence_enabled(request.arguments) else {},
        )


def computer_use_safe_result(*, request, report: ComputerUseExecutionReport) -> tuple[dict[str, object], bool]:
    raw_enabled = _raw_persistence_enabled(request.arguments)
    records = (
        persist_automation_artifacts(
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            capability_id=request.proposal.capability_ref.identifier,
            payloads=report.artifact_payloads,
        )
        if raw_enabled and report.artifact_payloads
        else {}
    )
    return (
        {
            "adapter": "windows-desktop-computer-use",
            "backend": report.backend,
            "tool_name": report.tool_name,
            "ufo_external_process": "operator_configured",
            "omniparser_external_process": "operator_configured",
            "live_execution": report.status == "succeeded",
            "action_count": report.action_count,
            "reason_code": report.reason_code,
            "approval_required": True,
            "approved_execution": request.approval_decision is not None,
            "credential_entry_allowed": True,
            "arbitrary_desktop_control_allowed": True,
            "raw_screen_persisted": "screen" in records,
            "raw_action_payload_persisted": "action_log" in records,
            "artifact_ids": {key: value.artifact_id for key, value in records.items()},
        },
        bool(records),
    )


async def _execute_windows_mcp(arguments: dict[str, object]) -> ComputerUseExecutionReport:
    config = WindowsMcpServerConfig.builtin()
    params = StdioServerParameters(command=config.command, args=list(config.args))
    async with stdio_client(params) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            tool_name = _select_windows_mcp_tool(arguments, tuple(str(tool.name) for tool in tools))
            if tool_name is None:
                return ComputerUseExecutionReport(status="failed", backend="windows-mcp", reason_code="windows_mcp_tool_not_found")
            result = await session.call_tool(tool_name, _windows_mcp_arguments(arguments))
            return ComputerUseExecutionReport(
                status="failed" if result.isError else "succeeded",
                backend="windows-mcp",
                tool_name=tool_name,
                action_count=1,
                artifact_payloads={
                    "action_log": {
                        "tool": tool_name,
                        "content_types": [str(getattr(content, "type", type(content).__name__)) for content in result.content],
                        "is_error": bool(result.isError),
                    }
                },
            )


def _select_windows_mcp_tool(arguments: dict[str, object], tool_names: tuple[str, ...]) -> str | None:
    action_kind = str(arguments.get("action_kind") or "inspect").lower()
    preferences = {
        "inspect": ("Snapshot", "Screenshot", "GetDesktop", "GetWindows", "Observe"),
        "screenshot": ("Screenshot", "Snapshot", "Observe"),
        "click": ("Click", "MouseClick", "click"),
        "type": ("Type", "InputText", "SendKeys", "Keyboard"),
        "hotkey": ("Hotkey", "SendKeys", "Keyboard"),
        "focus": ("Focus", "ActivateWindow", "Window"),
        "open_app": ("Open", "Launch", "Run"),
    }
    candidates = preferences.get(action_kind, (action_kind,))
    for preferred in candidates:
        for tool_name in tool_names:
            if preferred.lower() in tool_name.lower():
                return tool_name
    return tool_names[0] if tool_names else None


def _windows_mcp_arguments(arguments: dict[str, object]) -> dict[str, object]:
    blocked = {"approval_request_id", "approval_decision", "destructive_action_decision", "raw_persistence_enabled"}
    return {key: value for key, value in arguments.items() if key not in blocked}


def _raw_persistence_enabled(arguments: dict[str, object]) -> bool:
    if arguments.get("raw_persistence_enabled") is True:
        return True
    return os.environ.get("MARVEX_AUTOMATION_RAW_PERSISTENCE", "").strip().lower() in {"1", "true", "yes", "on"}


def _live_execution_enabled(arguments: dict[str, object]) -> bool:
    if arguments.get("live_execution_enabled") is True:
        return True
    return os.environ.get("MARVEX_OWNER_MODE_AUTOMATION", "").strip().lower() in {"1", "true", "yes", "on"}
