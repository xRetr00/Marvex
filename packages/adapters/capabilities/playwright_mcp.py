from __future__ import annotations

import asyncio
import importlib.util
import os
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from packages.automation_runtime import persist_automation_artifacts
from packages.capability_runtime import CapabilityExecutionRequest, CapabilityResultEnvelope


class PlaywrightMcpModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class PlaywrightMcpServerConfig(PlaywrightMcpModel):
    server_id: str = "playwright-mcp"
    command: str = "npx"
    args: tuple[str, ...] = ("@playwright/mcp@latest", "--browser=chrome")
    transport: Literal["stdio"] = "stdio"
    headed_by_default: bool = True
    browser: Literal["chrome", "msedge", "chromium", "firefox", "webkit"] = "chrome"
    extension_mode: bool = False
    cdp_endpoint: str | None = None
    unsafe_code_tools: tuple[str, ...] = ("browser_evaluate",)

    @classmethod
    def builtin(
        cls,
        *,
        browser: Literal["chrome", "msedge", "chromium", "firefox", "webkit"] = "chrome",
        extension_mode: bool = False,
        cdp_endpoint: str | None = None,
    ) -> "PlaywrightMcpServerConfig":
        # Pinnable for reproducibility/offline; defaults to latest. Set
        # MARVEX_PLAYWRIGHT_MCP_SPEC=@playwright/mcp@<version> to lock it.
        spec = (os.environ.get("MARVEX_PLAYWRIGHT_MCP_SPEC") or "@playwright/mcp@latest").strip()
        args: list[str] = [spec]
        if extension_mode:
            args.append("--extension")
        elif cdp_endpoint:
            args.append(f"--cdp-endpoint={cdp_endpoint}")
        else:
            args.append(f"--browser={browser}")
        return cls(
            args=tuple(args),
            browser=browser,
            extension_mode=extension_mode,
            cdp_endpoint=cdp_endpoint,
        )


class PlaywrightMcpExecutionReport(PlaywrightMcpModel):
    status: Literal["succeeded", "failed", "denied"] = "succeeded"
    backend: str = "playwright-mcp"
    tool_name: str = ""
    action_count: int = Field(default=0, ge=0)
    browser: str = "chrome"
    extension_mode: bool = False
    cdp_endpoint_present: bool = False
    reason_code: str | None = None
    install_dep_id: str | None = None
    missing_dependencies: tuple[str, ...] = ()
    artifact_payloads: dict[str, Any] = Field(default_factory=dict)


def execute_playwright_mcp_task(request: CapabilityExecutionRequest) -> PlaywrightMcpExecutionReport:
    if not _live_execution_enabled(request.arguments):
        return PlaywrightMcpExecutionReport(status="denied", reason_code="playwright_mcp_live_execution_not_enabled")
    config = _config_from_arguments(request.arguments)
    tool_name, tool_args = _tool_call_from_arguments(request.arguments)
    if not tool_name:
        return PlaywrightMcpExecutionReport(status="denied", reason_code="playwright_mcp_tool_required")
    if _unsafe_code_tool(tool_name) and request.arguments.get("unsafe_code_approved") is not True:
        return PlaywrightMcpExecutionReport(status="denied", reason_code="playwright_mcp_unsafe_code_requires_approval", tool_name=tool_name)
    if importlib.util.find_spec("mcp") is None:
        return PlaywrightMcpExecutionReport(
            status="denied",
            tool_name=tool_name,
            browser=config.browser,
            extension_mode=config.extension_mode,
            cdp_endpoint_present=bool(config.cdp_endpoint),
            reason_code="playwright_mcp_dependency_unavailable",
            install_dep_id="mcp",
            missing_dependencies=("mcp",),
        )
    try:
        return asyncio.run(_run_playwright_mcp(config, tool_name=tool_name, tool_args=tool_args))
    except Exception as exc:  # pragma: no cover - local MCP failures vary by machine
        return PlaywrightMcpExecutionReport(
            status="failed",
            tool_name=tool_name,
            browser=config.browser,
            extension_mode=config.extension_mode,
            cdp_endpoint_present=bool(config.cdp_endpoint),
            reason_code=f"playwright_mcp_execution_failed:{type(exc).__name__}",
            artifact_payloads={"error": repr(exc)} if _raw_persistence_enabled(request.arguments) else {},
        )


def playwright_mcp_safe_result(
    *,
    request: CapabilityExecutionRequest,
    report: PlaywrightMcpExecutionReport,
) -> tuple[dict[str, object], bool]:
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
            "adapter": "playwright-mcp",
            "backend": report.backend,
            "live_execution": report.status == "succeeded",
            "tool_name": report.tool_name,
            "action_count": report.action_count,
            "browser": report.browser,
            "extension_mode": report.extension_mode,
            "cdp_endpoint_present": report.cdp_endpoint_present,
            "reason_code": report.reason_code,
            "install_dep_id": report.install_dep_id,
            "missing_dependencies": report.missing_dependencies,
            "approval_required": True,
            "raw_playwright_payload_persisted": bool(records),
            "artifact_ids": {key: value.artifact_id for key, value in records.items()},
        },
        bool(records),
    )


async def _run_playwright_mcp(
    config: PlaywrightMcpServerConfig,
    *,
    tool_name: str,
    tool_args: dict[str, Any],
) -> PlaywrightMcpExecutionReport:
    # Lazy import so a missing mcp SDK can't break tool-worker import.
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server = StdioServerParameters(command=config.command, args=list(config.args))
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            available = {tool.name for tool in getattr(tools, "tools", ())}
            if tool_name not in available:
                return PlaywrightMcpExecutionReport(
                    status="denied",
                    tool_name=tool_name,
                    browser=config.browser,
                    extension_mode=config.extension_mode,
                    cdp_endpoint_present=bool(config.cdp_endpoint),
                    reason_code="playwright_mcp_tool_not_available",
                    artifact_payloads={"available_tools": sorted(available)},
                )
            result = await session.call_tool(tool_name, arguments=tool_args)
            return PlaywrightMcpExecutionReport(
                status="failed" if result.isError else "succeeded",
                tool_name=tool_name,
                action_count=1,
                browser=config.browser,
                extension_mode=config.extension_mode,
                cdp_endpoint_present=bool(config.cdp_endpoint),
                reason_code="playwright_mcp_tool_error" if result.isError else None,
                artifact_payloads={"tool_result": _safe_tool_result(result)},
            )


def _config_from_arguments(arguments: dict[str, object]) -> PlaywrightMcpServerConfig:
    browser = str(arguments.get("browser") or os.environ.get("MARVEX_PLAYWRIGHT_MCP_BROWSER") or "chrome")
    if browser not in {"chrome", "msedge", "chromium", "firefox", "webkit"}:
        browser = "chrome"
    extension_mode = arguments.get("extension_mode") is True
    cdp_endpoint = str(arguments.get("cdp_endpoint") or "").strip() or None
    # Prefer driving the user's REAL Chrome (their profile + logins) via CDP, the
    # same instance browser_use attaches to, instead of a throwaway Playwright
    # profile. Only when no explicit endpoint/extension mode is requested and the
    # caller hasn't opted out via MARVEX_PLAYWRIGHT_MCP_NO_CDP.
    if (
        cdp_endpoint is None
        and not extension_mode
        and os.environ.get("MARVEX_PLAYWRIGHT_MCP_NO_CDP", "").strip().lower() not in {"1", "true", "yes", "on"}
    ):
        try:
            from .chrome_cdp import ensure_debuggable_chrome

            resolved = ensure_debuggable_chrome()
            if resolved.get("cdp_url"):
                cdp_endpoint = str(resolved["cdp_url"])
        except Exception:
            cdp_endpoint = None
    return PlaywrightMcpServerConfig.builtin(
        browser=browser,  # type: ignore[arg-type]
        extension_mode=extension_mode,
        cdp_endpoint=cdp_endpoint,
    )


def _tool_call_from_arguments(arguments: dict[str, object]) -> tuple[str, dict[str, Any]]:
    tool_name = str(arguments.get("tool_name") or "").strip()
    raw_tool_args = arguments.get("tool_args")
    if isinstance(raw_tool_args, dict):
        return tool_name, dict(raw_tool_args)
    url = str(arguments.get("url") or "").strip()
    if not tool_name and url:
        return "browser_navigate", {"url": url}
    task = str(arguments.get("task") or "").strip()
    if not tool_name and task:
        match = re.search(r"https?://\S+", task)
        if match:
            return "browser_navigate", {"url": match.group(0).rstrip(".,)")}
    return tool_name, {}


def _unsafe_code_tool(tool_name: str) -> bool:
    normalized = tool_name.lower().replace("-", "_")
    return normalized in {"browser_evaluate", "evaluate", "browser_run_code"}


def _safe_tool_result(result: Any) -> dict[str, Any]:
    content = getattr(result, "content", ()) or ()
    return {
        "is_error": bool(getattr(result, "isError", False)),
        "content_count": len(content),
        "content_types": [str(getattr(item, "type", type(item).__name__)) for item in content],
        "structured_content_present": getattr(result, "structuredContent", None) is not None,
    }


def _raw_persistence_enabled(arguments: dict[str, object]) -> bool:
    if arguments.get("raw_persistence_enabled") is True:
        return True
    return os.environ.get("MARVEX_AUTOMATION_RAW_PERSISTENCE", "").strip().lower() in {"1", "true", "yes", "on"}


def _live_execution_enabled(arguments: dict[str, object]) -> bool:
    if arguments.get("live_execution_enabled") is True:
        return True
    return os.environ.get("MARVEX_OWNER_MODE_AUTOMATION", "").strip().lower() in {"1", "true", "yes", "on"}
