"""Built-in tool registry.

Replaces the ``if/elif`` dispatch ladders in ``builtins.py`` (and, in a later
increment, ``files.py``) with a single ``dict[identifier -> Tool]`` lookup.
The registry is the one place that:

* dispatches an execution request to the right tool,
* lists capability manifests for the platform,
* exposes model-facing JSON tool schemas for agentic tool-calling (docs/TODO/02).

One module per tool lives beside this file. To add a tool: create its module
with a ``Tool`` subclass and register it in ``default_registry`` (or pass it to
``ToolRegistry``).
"""

from __future__ import annotations

from packages.capability_runtime import (
    CapabilityExecutionRequest,
    CapabilityManifest,
    CapabilityResultEnvelope,
)

from .base import Tool, denied_result, succeeded_result
from .calculator import CalculatorTool
from .diagnostics import CapabilityDiagnosticsTool
from .list import ListDirectoryTool
from .memory import MemoryForgetTool, MemoryListRecentTool, MemoryRememberTool, MemorySearchTool
from .mcp import LocalMcpEchoTool
from .patch import PatchFileTool
from .read import ReadFileTool
from .repo_status import RepoStatusTool
from .ripgrep import RipgrepTool
from .search import SearchFilesTool
from .time_date import TimeDateTool
from .web_search import WebSearchTool
from .write import WriteFileTool


class ToolRegistry:
    """A lookup of built-in tools keyed by capability identifier."""

    def __init__(self, tools: tuple[Tool, ...]) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools:
            identifier = tool.tool_id()
            if identifier in self._tools:
                raise ValueError(f"duplicate tool identifier: {identifier}")
            self._tools[identifier] = tool

    def get(self, identifier: str) -> Tool | None:
        return self._tools.get(identifier)

    def tools(self) -> tuple[Tool, ...]:
        return tuple(self._tools.values())

    def manifests(self) -> tuple[CapabilityManifest, ...]:
        return tuple(tool.to_manifest() for tool in self._tools.values())

    def tool_schemas(self) -> tuple[dict[str, object], ...]:
        """OpenAI-style tool/function schemas for model tool-calling."""

        schemas: list[dict[str, object]] = []
        for tool in self._tools.values():
            schemas.append(
                {
                    "type": "function",
                    "function": {
                        "name": tool.tool_id(),
                        "description": tool.description,
                        "parameters": tool.json_schema(),
                    },
                }
            )
        return tuple(schemas)

    def execute(self, request: CapabilityExecutionRequest) -> CapabilityResultEnvelope:
        identifier = request.proposal.capability_ref.identifier
        tool = self._tools.get(identifier)
        if tool is None:
            return denied_result(request, reason_code="tool.unsupported_capability")
        return tool.execute(request)


def default_registry() -> ToolRegistry:
    """Construct the default built-in (non-filesystem) tool registry.

    Capability diagnostics is wired with a live counter so its reported count
    reflects the actual registered tool set rather than a hardcoded number.
    """

    diagnostics = CapabilityDiagnosticsTool()
    tools: tuple[Tool, ...] = (
        CalculatorTool(),
        TimeDateTool(),
        diagnostics,
        RepoStatusTool(),
    )
    registry = ToolRegistry(tools)
    diagnostics._count_provider = lambda: len(registry.tools())  # type: ignore[attr-defined]
    return registry


def file_tools_registry() -> ToolRegistry:
    """Construct the sandboxed filesystem tool registry.

    Dispatch target for the files.py executors. Read tools are read-only/safe;
    write + patch are write_local/medium and stay behind the approval boundary.
    """

    return ToolRegistry(
        (
            ReadFileTool(),
            ListDirectoryTool(),
            SearchFilesTool(),
            RipgrepTool(),
            WriteFileTool(),
            PatchFileTool(),
        )
    )


def memory_tools_registry(
    *,
    memory_store: object,
    memory_tree_runtime: object | None = None,
    session_ref: object | None = None,
    conversation_ref: object | None = None,
) -> ToolRegistry:
    """Construct agent-callable memory tools around injected memory backends."""

    return ToolRegistry(
        (
            MemorySearchTool(
                memory_store=memory_store,
                memory_tree_runtime=memory_tree_runtime,
                session_ref=session_ref,
                conversation_ref=conversation_ref,
            ),
            MemoryRememberTool(
                memory_store=memory_store,
                memory_tree_runtime=memory_tree_runtime,
                session_ref=session_ref,
                conversation_ref=conversation_ref,
            ),
            MemoryForgetTool(
                memory_store=memory_store,
                memory_tree_runtime=memory_tree_runtime,
                session_ref=session_ref,
                conversation_ref=conversation_ref,
            ),
            MemoryListRecentTool(
                memory_store=memory_store,
                memory_tree_runtime=memory_tree_runtime,
                session_ref=session_ref,
                conversation_ref=conversation_ref,
            ),
        )
    )


def mcp_tools_registry() -> ToolRegistry:
    """Construct agent-callable MCP tools that are already allowlisted."""

    return ToolRegistry((LocalMcpEchoTool(),))


__all__ = [
    "ToolRegistry",
    "default_registry",
    "file_tools_registry",
    "memory_tools_registry",
    "mcp_tools_registry",
    "Tool",
    "succeeded_result",
    "denied_result",
    "CalculatorTool",
    "TimeDateTool",
    "CapabilityDiagnosticsTool",
    "RepoStatusTool",
    "ReadFileTool",
    "ListDirectoryTool",
    "SearchFilesTool",
    "RipgrepTool",
    "WriteFileTool",
    "PatchFileTool",
    "WebSearchTool",
    "MemorySearchTool",
    "MemoryRememberTool",
    "MemoryForgetTool",
    "MemoryListRecentTool",
    "LocalMcpEchoTool",
]
