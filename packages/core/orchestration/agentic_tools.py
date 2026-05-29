"""Tool-execution engine for the agentic tool-calling loop (docs/TODO/02).

Maps model-issued tool calls (OpenAI-style ``{"id", "function": {"name",
"arguments"}}``) to capability executions against the tool registries, and
produces the OpenAI-style tool-result messages that get threaded back to the
provider for continuation.

Design constraints honored here:

* **Approval boundary intact.** Only ``SAFE`` tools auto-execute inside the
  loop. A risky tool call (write/patch/etc.) is *not* executed; it is reported
  as ``needs_approval`` so the caller can route it through the existing human
  approval path instead of silently performing a side effect.
* **No fabrication of capabilities.** Unknown tool names produce a tool-result
  message saying the tool does not exist, rather than guessing.
* **Pure + testable.** This module does not import the provider, fastapi, or the
  Core service. The caller supplies a ``request_builder`` that knows app
  specifics (sandbox root, trace/turn ids), keeping this engine decoupled.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable

from packages.adapters.capabilities.tools import ToolRegistry
from packages.capability_runtime import CapabilityExecutionRequest, ToolRiskLevel

# Builds an execution request for a resolved tool id + parsed arguments. The
# caller injects sandbox root, trace/turn ids, and an approved permission for
# safe tools. Returns None if it declines to build (treated as unknown).
RequestBuilder = Callable[[str, dict[str, Any]], CapabilityExecutionRequest | None]


@dataclass
class ToolCallResult:
    call_id: str
    tool_id: str
    status: str  # "succeeded" | "unknown" | "needs_approval" | "error"
    message: dict[str, Any]  # OpenAI-style {"role": "tool", ...}


@dataclass
class ToolStepOutcome:
    assistant_message: dict[str, Any]
    tool_messages: list[dict[str, Any]]
    results: list[ToolCallResult] = field(default_factory=list)

    @property
    def executed_tool_ids(self) -> list[str]:
        return [r.tool_id for r in self.results if r.status == "succeeded"]

    @property
    def needs_approval(self) -> list[ToolCallResult]:
        return [r for r in self.results if r.status == "needs_approval"]

    @property
    def all_messages(self) -> list[dict[str, Any]]:
        return [self.assistant_message, *self.tool_messages]


def parse_tool_arguments(raw: Any) -> dict[str, Any]:
    """Parse OpenAI tool-call arguments (a JSON string) into a dict."""

    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _tool_message(call_id: str, content: str) -> dict[str, Any]:
    return {"role": "tool", "tool_call_id": call_id, "content": content}


def execute_tool_calls(
    tool_calls: list[dict[str, Any]],
    *,
    registry: ToolRegistry,
    request_builder: RequestBuilder,
) -> ToolStepOutcome:
    """Execute a batch of model tool calls and build continuation messages.

    Returns an assistant message echoing the tool calls (required by the
    OpenAI message protocol), the per-call tool-result messages, and a
    structured result list the loop driver uses to decide whether to continue,
    pause for approval, or finalize.
    """

    assistant_message: dict[str, Any] = {
        "role": "assistant",
        "content": None,
        "tool_calls": list(tool_calls),
    }
    results: list[ToolCallResult] = []
    tool_messages: list[dict[str, Any]] = []

    for call in tool_calls:
        call_id = str(call.get("id") or f"call_{len(results)}")
        function = call.get("function") if isinstance(call, dict) else None
        function = function if isinstance(function, dict) else {}
        name = str(function.get("name") or "").strip()
        arguments = parse_tool_arguments(function.get("arguments"))

        tool = registry.get(name)
        if tool is None:
            content = (
                f"Tool '{name or '(unnamed)'}' does not exist. "
                "Only the listed tools are available."
            )
            results.append(ToolCallResult(call_id, name, "unknown", _tool_message(call_id, content)))
            tool_messages.append(results[-1].message)
            continue

        if tool.risk_level is not ToolRiskLevel.SAFE:
            content = (
                f"Tool '{name}' requires human approval before it can run. "
                "It was not executed automatically."
            )
            results.append(ToolCallResult(call_id, name, "needs_approval", _tool_message(call_id, content)))
            tool_messages.append(results[-1].message)
            continue

        request = request_builder(name, arguments)
        if request is None:
            content = f"Tool '{name}' could not be prepared for execution."
            results.append(ToolCallResult(call_id, name, "error", _tool_message(call_id, content)))
            tool_messages.append(results[-1].message)
            continue

        try:
            envelope = registry.execute(request)
            safe_result = dict(getattr(envelope, "safe_result", {}) or {})
            status = str(getattr(envelope, "status", "succeeded"))
            if status != "succeeded":
                content = f"Tool '{name}' did not complete: {safe_result.get('reason_code', status)}."
                results.append(ToolCallResult(call_id, name, "error", _tool_message(call_id, content)))
            else:
                content = json.dumps(safe_result, default=str)[:4000]
                results.append(ToolCallResult(call_id, name, "succeeded", _tool_message(call_id, content)))
        except Exception as exc:  # never let a tool crash the loop
            content = f"Tool '{name}' raised an error: {type(exc).__name__}."
            results.append(ToolCallResult(call_id, name, "error", _tool_message(call_id, content)))
        tool_messages.append(results[-1].message)

    return ToolStepOutcome(
        assistant_message=assistant_message,
        tool_messages=tool_messages,
        results=results,
    )


__all__ = [
    "RequestBuilder",
    "ToolCallResult",
    "ToolStepOutcome",
    "execute_tool_calls",
    "parse_tool_arguments",
]
