from __future__ import annotations

import atexit
import asyncio
import concurrent.futures
import importlib.util
import os
import re
import shutil
import sys
import threading
from pathlib import Path
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
        bundled_node = Path(_node_main_safe_path(os.environ.get("MARVEX_NODE_PATH", "").strip()))
        bundled_cli = Path(_node_main_safe_path(os.environ.get("MARVEX_PLAYWRIGHT_MCP_CLI", "").strip()))
        if bundled_node.is_file() and bundled_cli.is_file():
            command = _node_main_safe_path(str(bundled_node))
            args: list[str] = [_node_main_safe_path(str(bundled_cli))]
        else:
            # Development fallback. Packaged builds set the bundled node/CLI
            # environment paths so runtime execution never depends on npm/npx.
            command = "npx"
            spec = (os.environ.get("MARVEX_PLAYWRIGHT_MCP_SPEC") or "@playwright/mcp@latest").strip()
            args = [spec]
        if extension_mode:
            args.append("--extension")
        elif cdp_endpoint:
            args.append(f"--cdp-endpoint={cdp_endpoint}")
        else:
            args.append(f"--browser={browser}")
        return cls(
            command=command,
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


class _PersistentPlaywrightMcpSession:
    """Long-lived stdio MCP session so chained browser calls share tab state."""

    def __init__(self, config: PlaywrightMcpServerConfig) -> None:
        self.config = config
        self.loop: asyncio.AbstractEventLoop | None = None
        self.queue: asyncio.Queue[tuple[str, dict[str, Any], concurrent.futures.Future[PlaywrightMcpExecutionReport]] | None] | None = None
        self.ready = threading.Event()
        self.error: BaseException | None = None
        self.thread = threading.Thread(target=self._thread_main, name="marvex-playwright-mcp", daemon=True)
        self.thread.start()

    def _thread_main(self) -> None:
        loop = asyncio.ProactorEventLoop() if os.name == "nt" else asyncio.new_event_loop()
        self.loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._worker())
        except BaseException as exc:  # pragma: no cover - local process failures vary
            self.error = exc
            self.ready.set()
        finally:
            loop.close()
            asyncio.set_event_loop(None)

    async def _worker(self) -> None:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client

        command, args = _resolve_stdio_command(self.config)
        server = StdioServerParameters(command=command, args=args)
        self.queue = asyncio.Queue()
        async with stdio_client(server) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                self.ready.set()
                while True:
                    item = await self.queue.get()
                    if item is None:
                        return
                    tool_name, tool_args, future = item
                    try:
                        future.set_result(await _call_playwright_mcp_tool(self.config, session, tool_name=tool_name, tool_args=tool_args))
                    except BaseException as exc:
                        future.set_exception(exc)

    def call(self, *, tool_name: str, tool_args: dict[str, Any], timeout: float = 180.0) -> PlaywrightMcpExecutionReport:
        if not self.ready.wait(timeout=30.0):
            raise TimeoutError("playwright_mcp_session_start_timeout")
        if self.error is not None:
            raise self.error
        if self.loop is None or self.queue is None:
            raise RuntimeError("playwright_mcp_session_unavailable")
        future: concurrent.futures.Future[PlaywrightMcpExecutionReport] = concurrent.futures.Future()
        self.loop.call_soon_threadsafe(self.queue.put_nowait, (tool_name, tool_args, future))
        return future.result(timeout=timeout)

    def close(self) -> None:
        if self.loop is not None and self.queue is not None and self.thread.is_alive():
            self.loop.call_soon_threadsafe(self.queue.put_nowait, None)
            self.thread.join(timeout=5.0)


_PERSISTENT_SESSIONS: dict[tuple[str, tuple[str, ...]], _PersistentPlaywrightMcpSession] = {}
_PERSISTENT_SESSIONS_LOCK = threading.Lock()
_MAX_PERSISTENT_SESSIONS = 4


def _close_persistent_sessions() -> None:
    with _PERSISTENT_SESSIONS_LOCK:
        sessions = list(_PERSISTENT_SESSIONS.values())
        _PERSISTENT_SESSIONS.clear()
    for session in sessions:
        session.close()


atexit.register(_close_persistent_sessions)


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
    # Preflight the launcher binary (npx/uvx). The MCP stdio client spawns it
    # without a shell, so a missing Node/npx surfaces as a raw OSError mid-run.
    # Detect it up front and report a clean, actionable dependency error.
    if shutil.which(config.command) is None:
        return PlaywrightMcpExecutionReport(
            status="denied",
            tool_name=tool_name,
            browser=config.browser,
            extension_mode=config.extension_mode,
            cdp_endpoint_present=bool(config.cdp_endpoint),
            reason_code="playwright_mcp_dependency_unavailable",
            install_dep_id="node" if config.command in {"npx", "node"} else config.command,
            missing_dependencies=(config.command,),
        )
    try:
        return _run_playwright_mcp_sync(config, tool_name=tool_name, tool_args=tool_args)
    except Exception as exc:  # pragma: no cover - local MCP failures vary by machine
        # The concrete failure (e.g. a Windows spawn OSError) is otherwise lost,
        # so write the traceback to stderr where the worker log captures it.
        import traceback

        print(
            f"playwright_mcp execution failed: {exc!r}\n{traceback.format_exc()}",
            file=sys.stderr,
            flush=True,
        )
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


def _run_playwright_mcp_sync(
    config: PlaywrightMcpServerConfig,
    *,
    tool_name: str,
    tool_args: dict[str, Any],
) -> PlaywrightMcpExecutionReport:
    """Run through a long-lived subprocess-capable MCP session."""

    key = (config.command, config.args)
    with _PERSISTENT_SESSIONS_LOCK:
        session = _PERSISTENT_SESSIONS.get(key)
        if session is None:
            if len(_PERSISTENT_SESSIONS) >= _MAX_PERSISTENT_SESSIONS:
                oldest_key = next(iter(_PERSISTENT_SESSIONS))
                _PERSISTENT_SESSIONS.pop(oldest_key).close()
            session = _PersistentPlaywrightMcpSession(config)
            _PERSISTENT_SESSIONS[key] = session
    try:
        return session.call(tool_name=tool_name, tool_args=tool_args)
    except Exception:
        with _PERSISTENT_SESSIONS_LOCK:
            if _PERSISTENT_SESSIONS.get(key) is session:
                _PERSISTENT_SESSIONS.pop(key, None)
        session.close()
        raise


async def _run_playwright_mcp(
    config: PlaywrightMcpServerConfig,
    *,
    tool_name: str,
    tool_args: dict[str, Any],
) -> PlaywrightMcpExecutionReport:
    # Lazy import so a missing mcp SDK can't break tool-worker import.
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    command, args = _resolve_stdio_command(config)
    server = StdioServerParameters(command=command, args=args)
    async with stdio_client(server) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            return await _call_playwright_mcp_tool(config, session, tool_name=tool_name, tool_args=tool_args)


async def _call_playwright_mcp_tool(
    config: PlaywrightMcpServerConfig,
    session: Any,
    *,
    tool_name: str,
    tool_args: dict[str, Any],
) -> PlaywrightMcpExecutionReport:
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
    reason_code = _tool_error_reason(result) if result.isError else None
    return PlaywrightMcpExecutionReport(
        status="failed" if result.isError else "succeeded",
        tool_name=tool_name,
        action_count=1,
        browser=config.browser,
        extension_mode=config.extension_mode,
        cdp_endpoint_present=bool(config.cdp_endpoint),
        reason_code=reason_code,
        install_dep_id="playwright_extension" if reason_code == "playwright_mcp_extension_not_found" else None,
        missing_dependencies=("playwright_extension",) if reason_code == "playwright_mcp_extension_not_found" else (),
        artifact_payloads={"tool_result": _safe_tool_result(result)},
    )


def _resolve_stdio_command(config: PlaywrightMcpServerConfig) -> tuple[str, list[str]]:
    """Resolve the stdio launch command for the current platform.

    On Windows, ``npx`` (and ``uvx``) are ``.cmd`` shims that the shell-less MCP
    stdio client cannot exec directly -- doing so raises ``OSError``/``WinError
    193``. Route those through ``cmd /c`` so the shim is interpreted correctly.
    """

    command = _node_main_safe_path(config.command)
    args = [_node_main_safe_path(arg) for arg in config.args]
    if os.name == "nt":
        resolved = shutil.which(command)
        if resolved and resolved.lower().endswith(".exe"):
            return resolved, args
        if resolved is None or resolved.lower().endswith((".cmd", ".bat")):
            shell = os.environ.get("COMSPEC", "").strip() or shutil.which("cmd") or "cmd.exe"
            return shell, ["/d", "/c", resolved or command, *args]
    return command, args


def _node_main_safe_path(path: str) -> str:
    r"""Node v24 cannot use Windows verbatim paths as the main script.

    Tauri/resource paths can arrive as ``\\?\D:\...``. Passing that path as
    Node's entrypoint reproduces the live failure ``EISDIR: lstat 'D:'`` and the
    MCP client then reports only ``Connection closed`` / ``ExceptionGroup``.
    Normalize before launching Node while leaving non-path arguments unchanged.
    """

    if os.name != "nt":
        return path
    if path.startswith("\\\\?\\UNC\\"):
        return "\\\\" + path[len("\\\\?\\UNC\\") :]
    if path.startswith("\\\\?\\"):
        return path[len("\\\\?\\") :]
    return path


def _config_from_arguments(arguments: dict[str, object]) -> PlaywrightMcpServerConfig:
    browser = str(arguments.get("browser") or os.environ.get("MARVEX_PLAYWRIGHT_MCP_BROWSER") or "chrome")
    if browser not in {"chrome", "msedge", "chromium", "firefox", "webkit"}:
        browser = "chrome"
    explicit_extension_mode = arguments.get("extension_mode")
    extension_mode = explicit_extension_mode is True
    cdp_endpoint = str(arguments.get("cdp_endpoint") or "").strip() or None
    extension_disabled = os.environ.get("MARVEX_PLAYWRIGHT_MCP_NO_EXTENSION", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if (
        explicit_extension_mode is None
        and cdp_endpoint is None
        and browser in {"chrome", "msedge"}
        and not extension_disabled
    ):
        # Playwright's extension is the supported way to attach to an already
        # open Chrome/Edge profile and reuse its logged-in sessions.
        extension_mode = True
    # CDP remains available for explicit custom profiles and older deployments
    # that opt out of extension mode.
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


def _tool_error_reason(result: Any) -> str:
    text = " ".join(
        str(getattr(item, "text", "") or "")
        for item in (getattr(result, "content", ()) or ())
    ).lower()
    if "playwright extension not found" in text:
        return "playwright_mcp_extension_not_found"
    return "playwright_mcp_tool_error"


def _raw_persistence_enabled(arguments: dict[str, object]) -> bool:
    if arguments.get("raw_persistence_enabled") is True:
        return True
    return os.environ.get("MARVEX_AUTOMATION_RAW_PERSISTENCE", "").strip().lower() in {"1", "true", "yes", "on"}


def _live_execution_enabled(arguments: dict[str, object]) -> bool:
    if arguments.get("live_execution_enabled") is True:
        return True
    return os.environ.get("MARVEX_OWNER_MODE_AUTOMATION", "").strip().lower() in {"1", "true", "yes", "on"}
