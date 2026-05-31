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
from packages.adapters.capabilities.tools.clarify import CLARIFY_TOOL_ID, clarification_payload_from_arguments
from packages.adapters.capabilities.tools.automation import AUTOMATION_TOOL_CAPABILITIES
from packages.capability_runtime import CapabilityExecutionRequest, ToolRiskLevel

# Builds an execution request for a resolved tool id + parsed arguments. The
# caller injects sandbox root, trace/turn ids, and an approved permission for
# safe tools. Returns None if it declines to build (treated as unknown).
RequestBuilder = Callable[[str, dict[str, Any]], CapabilityExecutionRequest | None]


@dataclass
class ToolCallResult:
    call_id: str
    tool_id: str
    status: str  # "succeeded" | "unknown" | "needs_approval" | "needs_clarification" | "error"
    message: dict[str, Any]  # OpenAI-style {"role": "tool", ...}
    clarification: dict[str, Any] | None = None  # set when status == "needs_clarification"
    automation: dict[str, Any] | None = None  # set when an automation tool needs approval


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
    def needs_clarification(self) -> list[ToolCallResult]:
        return [r for r in self.results if r.status == "needs_clarification"]

    @property
    def automation_calls(self) -> list[ToolCallResult]:
        return [r for r in self.results if r.automation is not None]

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
        # Tool schemas advertise control tools as "builtin.<id>" (e.g.
        # builtin.clarify, builtin.browser_use), so the model calls that form.
        # Compare interception ids against the bare id, not the namespaced name.
        bare_name = name[len("builtin.") :] if name.startswith("builtin.") else name

        if bare_name == CLARIFY_TOOL_ID:
            # Model-driven clarification: do not execute anything; pause the turn
            # and surface the question to the user via the UI.
            payload = clarification_payload_from_arguments(arguments)
            content = "Awaiting the user's answer to the clarifying question."
            results.append(
                ToolCallResult(call_id, name, "needs_clarification", _tool_message(call_id, content), clarification=payload)
            )
            tool_messages.append(results[-1].message)
            continue

        if bare_name in AUTOMATION_TOOL_CAPABILITIES:
            # Model called a browser/desktop automation tool. Do not execute it in
            # the loop: pause for human approval and carry the capability id + the
            # model's arguments so Core executes the real capability on approve.
            capability_id, resource_type, capability_label = AUTOMATION_TOOL_CAPABILITIES[bare_name]
            content = f"Tool '{name}' requires human approval before it can run. Awaiting approval."
            results.append(
                ToolCallResult(
                    call_id,
                    name,
                    "needs_approval",
                    _tool_message(call_id, content),
                    automation={
                        "tool_id": name,
                        "capability_id": capability_id,
                        "resource_type": resource_type,
                        "capability": capability_label,
                        "arguments": arguments,
                    },
                )
            )
            tool_messages.append(results[-1].message)
            continue

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


@dataclass
class ProviderStep:
    """The subset of a provider response the loop driver needs."""

    output_text: str
    tool_calls: list[dict[str, Any]]
    response_id: str | None
    error: bool


@dataclass
class LoopResult:
    status: str  # "final" | "needs_approval" | "needs_clarification" | "error" | "max_steps"
    text: str
    steps: int
    executed_tool_ids: list[str] = field(default_factory=list)
    needs_approval_tool_ids: list[str] = field(default_factory=list)
    clarification: dict[str, Any] | None = None  # set when status == "needs_clarification"
    automation: dict[str, Any] | None = None  # capability+args when an automation tool needs approval
    response_id: str | None = None  # provider response id at pause (for resume)


# send(input_text, tool_messages, previous_response_id) -> ProviderStep
SendFn = Callable[[str, list[dict[str, Any]] | None, str | None], ProviderStep]


def run_tool_loop(
    *,
    send: SendFn,
    registry: ToolRegistry,
    request_builder: RequestBuilder,
    max_steps: int,
    initial_input: str,
    previous_response_id: str | None = None,
) -> LoopResult:
    """Drive the model<->tools loop until a text answer, approval, or limit.

    Pure and provider-agnostic: ``send`` is a caller-supplied callable that
    performs one provider round trip and returns a ``ProviderStep``. This keeps
    the loop unit-testable without the provider, fastapi, or Core service.

    Termination:
      * model returns no tool calls           -> status "final"
      * a risky tool needs approval           -> status "needs_approval"
      * provider error                        -> status "error"
      * max_steps exhausted with tool calls   -> status "max_steps"
    """

    steps = max(1, int(max_steps))
    prev = previous_response_id
    tool_messages: list[dict[str, Any]] | None = None
    input_text = initial_input
    executed: list[str] = []
    last_text = ""

    for index in range(steps):
        step = send(input_text, tool_messages, prev)
        if step.error:
            return LoopResult(status="error", text=last_text, steps=index + 1, executed_tool_ids=executed)
        last_text = step.output_text or last_text
        if step.response_id:
            prev = step.response_id
        if not step.tool_calls:
            return LoopResult(status="final", text=last_text, steps=index + 1, executed_tool_ids=executed)
        outcome = execute_tool_calls(
            step.tool_calls, registry=registry, request_builder=request_builder
        )
        executed.extend(outcome.executed_tool_ids)
        if outcome.needs_clarification:
            return LoopResult(
                status="needs_clarification",
                text=last_text,
                steps=index + 1,
                executed_tool_ids=executed,
                clarification=outcome.needs_clarification[0].clarification,
                response_id=prev,
            )
        if outcome.needs_approval:
            automation_calls = outcome.automation_calls
            return LoopResult(
                status="needs_approval",
                text=last_text,
                steps=index + 1,
                executed_tool_ids=executed,
                needs_approval_tool_ids=[r.tool_id for r in outcome.needs_approval],
                automation=automation_calls[0].automation if automation_calls else None,
                response_id=prev,
            )
        tool_messages = outcome.all_messages
        input_text = ""  # continuation: provider uses tool_messages

    return LoopResult(status="max_steps", text=last_text, steps=steps, executed_tool_ids=executed)


__all__ = [
    "RequestBuilder",
    "ToolCallResult",
    "ToolStepOutcome",
    "ProviderStep",
    "LoopResult",
    "SendFn",
    "execute_tool_calls",
    "parse_tool_arguments",
    "run_tool_loop",
]
