"""Tool-execution engine for the agentic tool-calling loop (docs/TODO/02).

Maps model-issued tool calls (OpenAI-style ``{"id", "function": {"name",
"arguments"}}``) to capability executions against the tool registries, and
produces the OpenAI-style tool-result messages that get threaded back to the
provider for continuation.

Design constraints honored here:

* **Approval boundary intact.** Safe read/network tools auto-execute inside the
  loop. A risky or local/browser/desktop side-effect tool call is reported as
  ``needs_approval`` so the caller can route it through policy/human approval.
* **No fabrication of capabilities.** Unknown tool names produce a tool-result
  message saying the tool does not exist, rather than guessing.
* **Pure + testable.** This module does not import the provider, fastapi, or the
  Core service. The caller supplies a ``request_builder`` that knows app
  specifics (sandbox root, trace/turn ids), keeping this engine decoupled.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from packages.adapters.capabilities.tools import ToolRegistry
from packages.adapters.capabilities.tools.base import Tool
from packages.adapters.capabilities.tools.clarify import CLARIFY_TOOL_ID, clarification_payload_from_arguments
from packages.adapters.capabilities.tools.automation import AUTOMATION_TOOL_CAPABILITIES
from packages.capability_runtime import CapabilityExecutionRequest, ToolRiskLevel, ToolSideEffectLevel

_APPROVAL_SIDE_EFFECTS = {
    ToolSideEffectLevel.WRITE_LOCAL,
    ToolSideEffectLevel.BROWSER_ACTION,
    ToolSideEffectLevel.DESKTOP_ACTION,
    ToolSideEffectLevel.CREDENTIAL_ACTION,
    ToolSideEffectLevel.PURCHASE_OR_PAYMENT,
    ToolSideEffectLevel.DESTRUCTIVE,
}

# Builds an execution request for a resolved tool id + parsed arguments. The
# caller injects sandbox root, trace/turn ids, and an approved permission for
# safe tools. Returns None if it declines to build (treated as unknown).
RequestBuilder = Callable[[str, dict[str, Any]], CapabilityExecutionRequest | None]
FailureAttemptCounter = Callable[[str, str], tuple[int, int]]


@dataclass
class ToolCallResult:
    call_id: str
    tool_id: str
    status: str  # "succeeded" | "unknown" | "needs_approval" | "needs_clarification" | "error"
    message: dict[str, Any]  # OpenAI-style {"role": "tool", ...}
    clarification: dict[str, Any] | None = None  # set when status == "needs_clarification"
    automation: dict[str, Any] | None = None  # set when an automation tool needs approval
    pending_tool: dict[str, Any] | None = None  # model-authored tool call to resume after approval


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
    def pending_tool_calls(self) -> list[ToolCallResult]:
        return [r for r in self.results if r.pending_tool is not None]

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


def _failure_guidance(tool_name: str, reason: str, failure_attempt_counter: FailureAttemptCounter | None) -> str:
    attempt, max_attempts = failure_attempt_counter(tool_name, reason) if failure_attempt_counter is not None else (1, 5)
    if attempt >= max_attempts:
        return (
            f"Recovery guidance: failure attempt {attempt} of {max_attempts}. "
            "Do not keep retrying the same failed tool path. If another available tool can solve the request, call it now; "
            "otherwise tell the user the real failure reason and what is needed next."
        )
    return (
        f"Recovery guidance: failure attempt {attempt} of {max_attempts}. "
        "Try again with corrected arguments if that can solve the request. If another available tool is better, call that tool instead. "
        "Do not claim success until a tool result succeeds."
    )


def _tool_failure_message(
    tool_name: str,
    reason: str,
    message: str,
    failure_attempt_counter: FailureAttemptCounter | None,
) -> str:
    return f"{message}\n{_failure_guidance(tool_name or 'unknown_tool', reason, failure_attempt_counter)}"


def _validated_tool_arguments(tool: Tool | None, arguments: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    if tool is None:
        return dict(arguments), None
    if tool.tool_id().startswith("file."):
        # File tools receive the configured sandbox root from Core's request
        # builder, not from the model. Their adapters validate root/path/content
        # at execution time after that injection.
        return dict(arguments), None
    try:
        validated = tool.params_model.model_validate(arguments)
    except Exception as exc:
        return None, f"invalid_arguments:{type(exc).__name__}"
    return dict(validated.model_dump(mode="json")), None


def execute_tool_calls(
    tool_calls: list[dict[str, Any]],
    *,
    registry: ToolRegistry,
    request_builder: RequestBuilder,
    prior_tool_messages: list[dict[str, Any]] | None = None,
    failure_attempt_counter: FailureAttemptCounter | None = None,
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
            validated_arguments, validation_reason = _validated_tool_arguments(registry.get(name), arguments)
            if validated_arguments is None:
                content = _tool_failure_message(
                    name,
                    validation_reason or "invalid_arguments",
                    f"Tool '{name}' arguments are invalid ({validation_reason}). Call the tool again with arguments matching its schema.",
                    failure_attempt_counter,
                )
                results.append(ToolCallResult(call_id, name, "error", _tool_message(call_id, content)))
                tool_messages.append(results[-1].message)
                continue
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
                        "arguments": validated_arguments,
                    },
                    pending_tool={
                        "tool_id": name,
                        "capability_id": capability_id,
                        "resource_type": resource_type,
                        "capability": capability_label,
                        "arguments": validated_arguments,
                        "call_id": call_id,
                    },
                )
            )
            tool_messages.append(results[-1].message)
            continue

        tool = registry.get(name)
        if tool is None:
            content = _tool_failure_message(
                name or "unknown_tool",
                "unknown_tool",
                f"Tool '{name or '(unnamed)'}' does not exist. Only the listed tools are available.",
                failure_attempt_counter,
            )
            results.append(ToolCallResult(call_id, name, "unknown", _tool_message(call_id, content)))
            tool_messages.append(results[-1].message)
            continue

        validated_arguments, validation_reason = _validated_tool_arguments(tool, arguments)
        if validated_arguments is None:
            content = _tool_failure_message(
                name,
                validation_reason or "invalid_arguments",
                f"Tool '{name}' arguments are invalid ({validation_reason}). Call the tool again with arguments matching its schema.",
                failure_attempt_counter,
            )
            results.append(ToolCallResult(call_id, name, "error", _tool_message(call_id, content)))
            tool_messages.append(results[-1].message)
            continue
        arguments = validated_arguments

        grounding_retry = _web_grounded_write_retry_message(name, arguments, prior_tool_messages)
        if grounding_retry is not None:
            content = _tool_failure_message(name, "web_grounded_write_missing_source_url", grounding_retry, failure_attempt_counter)
            results.append(ToolCallResult(call_id, name, "error", _tool_message(call_id, content)))
            tool_messages.append(results[-1].message)
            continue

        if _tool_requires_approval(tool):
            content = (
                f"Tool '{name}' requires human approval before it can run. "
                "It was not executed automatically."
            )
            results.append(
                ToolCallResult(
                    call_id,
                    name,
                    "needs_approval",
                    _tool_message(call_id, content),
                    pending_tool={
                        "tool_id": name,
                        "capability_id": name,
                        "resource_type": _resource_type_for_tool(name),
                        "capability": _capability_label_for_tool(name),
                        "arguments": arguments,
                        "call_id": call_id,
                    },
                )
            )
            tool_messages.append(results[-1].message)
            continue

        request = request_builder(name, arguments)
        if request is None:
            content = _tool_failure_message(
                name,
                "tool_request_prepare_failed",
                f"Tool '{name}' could not be prepared for execution.",
                failure_attempt_counter,
            )
            results.append(ToolCallResult(call_id, name, "error", _tool_message(call_id, content)))
            tool_messages.append(results[-1].message)
            continue

        try:
            envelope = registry.execute(request)
            safe_result = dict(getattr(envelope, "safe_result", {}) or {})
            status = str(getattr(envelope, "status", "succeeded"))
            if status != "succeeded":
                reason = str(safe_result.get("reason_code") or status)
                content = _tool_failure_message(
                    name,
                    reason,
                    f"Tool '{name}' did not complete: {reason}.",
                    failure_attempt_counter,
                )
                results.append(ToolCallResult(call_id, name, "error", _tool_message(call_id, content)))
            else:
                content = json.dumps(safe_result, default=str)[:4000]
                results.append(ToolCallResult(call_id, name, "succeeded", _tool_message(call_id, content)))
        except Exception as exc:  # never let a tool crash the loop
            reason = f"exception:{type(exc).__name__}"
            content = _tool_failure_message(
                name,
                reason,
                f"Tool '{name}' raised an error: {type(exc).__name__}.",
                failure_attempt_counter,
            )
            results.append(ToolCallResult(call_id, name, "error", _tool_message(call_id, content)))
        tool_messages.append(results[-1].message)

    return ToolStepOutcome(
        assistant_message=assistant_message,
        tool_messages=tool_messages,
        results=results,
    )


def _tool_requires_approval(tool: Tool) -> bool:
    if tool.risk_level is not ToolRiskLevel.SAFE:
        return True
    return tool.side_effect_level in _APPROVAL_SIDE_EFFECTS


def _web_grounded_write_retry_message(
    tool_id: str,
    arguments: dict[str, Any],
    prior_tool_messages: list[dict[str, Any]] | None,
) -> str | None:
    if tool_id not in {"file.write", "file.patch"}:
        return None
    content = str(arguments.get("content") or "")
    if not content.strip():
        return None
    source_urls = _web_source_urls_from_messages(prior_tool_messages)
    if not source_urls:
        return None
    if any(url and url in content for url in source_urls):
        return None
    return (
        "This file write follows a successful web.search result, but the file "
        "content does not include at least one source URL from the search "
        "results. Call file.write again with grounded content that includes at "
        "least one source URL, or say plainly that the search evidence was not "
        "usable."
    )


def _web_source_urls_from_messages(messages: list[dict[str, Any]] | None) -> list[str]:
    urls: list[str] = []
    for message in messages or []:
        if message.get("role") != "tool":
            continue
        raw_content = message.get("content")
        if not isinstance(raw_content, str) or "web_search" not in raw_content:
            continue
        try:
            payload = json.loads(raw_content)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict) or payload.get("operation") != "web_search":
            continue
        if int(payload.get("result_count") or 0) <= 0:
            continue
        for result in payload.get("results") or []:
            if isinstance(result, dict):
                url = str(result.get("url") or "").strip()
                if url:
                    urls.append(url)
        for evidence in payload.get("evidence_refs") or []:
            if isinstance(evidence, dict):
                url = str(evidence.get("url") or "").strip()
                if url:
                    urls.append(url)
    return list(dict.fromkeys(urls))


def _resource_type_for_tool(tool_id: str) -> str:
    if tool_id.startswith("file."):
        return "file"
    if tool_id.startswith("memory."):
        return "memory"
    if tool_id.startswith("browser") or "browser" in tool_id:
        return "browser"
    if "computer" in tool_id:
        return "desktop"
    return "tool"


def _capability_label_for_tool(tool_id: str) -> str:
    if tool_id in {"file.write", "file.patch"}:
        return "file_write"
    if tool_id in {"memory.remember", "memory.forget"}:
        return "memory_auto_write"
    if tool_id.startswith("file."):
        return "read"
    if tool_id.startswith("memory."):
        return "memory_search"
    return tool_id.replace(".", "_")


@dataclass
class ProviderStep:
    """The subset of a provider response the loop driver needs."""

    output_text: str
    tool_calls: list[dict[str, Any]]
    response_id: str | None
    error: bool
    usage: dict[str, Any] = field(default_factory=dict)


@dataclass
class LoopResult:
    status: str  # "final" | "needs_approval" | "needs_clarification" | "error" | "max_steps"
    text: str
    steps: int
    executed_tool_ids: list[str] = field(default_factory=list)
    needs_approval_tool_ids: list[str] = field(default_factory=list)
    clarification: dict[str, Any] | None = None  # set when status == "needs_clarification"
    automation: dict[str, Any] | None = None  # capability+args when an automation tool needs approval
    pending_tool: dict[str, Any] | None = None  # capability+args when any model-authored tool needs approval
    response_id: str | None = None  # provider response id at pause (for resume)
    commentary: list[str] = field(default_factory=list)
    usage: dict[str, Any] = field(default_factory=dict)


# send(input_text, tool_messages, previous_response_id) -> ProviderStep
SendFn = Callable[[str, list[dict[str, Any]] | None, str | None], ProviderStep]
ToolDebugCallback = Callable[[int, ToolStepOutcome], None]

_THINK_BLOCK_RE = re.compile(r"<think>[\s\S]*?</think>", re.IGNORECASE)
_OPEN_THINK_RE = re.compile(r"<think>[\s\S]*$", re.IGNORECASE)
_FINAL_ANSWER_REPAIR_PROMPT = (
    "Provide the final user-facing answer now. Do not include analysis, hidden reasoning, "
    "or a <think> block. Answer the user's request directly."
)


def has_user_visible_text(text: str) -> bool:
    """True when provider text contains content outside private think blocks."""

    without_closed = _THINK_BLOCK_RE.sub(" ", text or "")
    without_open = _OPEN_THINK_RE.sub(" ", without_closed)
    return bool(without_open.strip())


def user_visible_text(text: str) -> str:
    """Return provider text outside private think blocks."""

    without_closed = _THINK_BLOCK_RE.sub(" ", text or "")
    return _OPEN_THINK_RE.sub(" ", without_closed).strip()


def _merge_usage(total: dict[str, Any], usage: dict[str, Any]) -> dict[str, Any]:
    merged = dict(total)
    for key, value in usage.items():
        if isinstance(value, bool):
            continue
        if isinstance(value, int | float):
            prior = merged.get(key)
            merged[key] = (prior if isinstance(prior, int | float) and not isinstance(prior, bool) else 0) + value
        elif isinstance(value, dict):
            prior = merged.get(key)
            merged[key] = _merge_usage(prior if isinstance(prior, dict) else {}, value)
    return merged


def run_tool_loop(
    *,
    send: SendFn,
    registry: ToolRegistry,
    request_builder: RequestBuilder,
    max_steps: int,
    initial_input: str,
    previous_response_id: str | None = None,
    initial_tool_messages: list[dict[str, Any]] | None = None,
    debug_callback: ToolDebugCallback | None = None,
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
    tool_messages: list[dict[str, Any]] | None = list(initial_tool_messages) if initial_tool_messages else None
    input_text = "" if tool_messages else initial_input
    executed: list[str] = []
    last_text = ""
    reasoning_only_retry_used = False
    commentary: list[str] = []
    usage: dict[str, Any] = {}
    failure_counts: dict[tuple[str, str], int] = {}

    def count_failure(tool_name: str, reason: str) -> tuple[int, int]:
        key = (tool_name, reason)
        failure_counts[key] = failure_counts.get(key, 0) + 1
        return failure_counts[key], 5

    for index in range(steps):
        step = send(input_text, tool_messages, prev)
        usage = _merge_usage(usage, step.usage)
        if step.error:
            return LoopResult(status="error", text=last_text, steps=index + 1, executed_tool_ids=executed, response_id=prev, commentary=commentary, usage=usage)
        last_text = step.output_text or last_text
        if step.response_id:
            prev = step.response_id
        if not step.tool_calls:
            if step.output_text and not has_user_visible_text(step.output_text) and not reasoning_only_retry_used:
                reasoning_only_retry_used = True
                input_text = _FINAL_ANSWER_REPAIR_PROMPT
                tool_messages = None
                continue
            return LoopResult(status="final", text=last_text, steps=index + 1, executed_tool_ids=executed, response_id=prev, commentary=commentary, usage=usage)
        visible_commentary = user_visible_text(step.output_text)
        if visible_commentary:
            commentary.append(visible_commentary)
        outcome = execute_tool_calls(
            step.tool_calls,
            registry=registry,
            request_builder=request_builder,
            prior_tool_messages=tool_messages,
            failure_attempt_counter=count_failure,
        )
        if debug_callback is not None:
            try:
                debug_callback(index + 1, outcome)
            except Exception:
                pass
        executed.extend(outcome.executed_tool_ids)
        if outcome.needs_clarification:
            return LoopResult(
                status="needs_clarification",
                text=last_text,
                steps=index + 1,
                executed_tool_ids=executed,
                clarification=outcome.needs_clarification[0].clarification,
                response_id=prev,
                commentary=commentary,
                usage=usage,
            )
        if outcome.needs_approval:
            automation_calls = outcome.automation_calls
            pending_calls = outcome.pending_tool_calls
            return LoopResult(
                status="needs_approval",
                text=last_text,
                steps=index + 1,
                executed_tool_ids=executed,
                needs_approval_tool_ids=[r.tool_id for r in outcome.needs_approval],
                automation=automation_calls[0].automation if automation_calls else None,
                pending_tool=pending_calls[0].pending_tool if pending_calls else None,
                response_id=prev,
                commentary=commentary,
                usage=usage,
            )
        tool_messages = outcome.all_messages
        input_text = ""  # continuation: provider uses tool_messages

    return LoopResult(status="max_steps", text=last_text, steps=steps, executed_tool_ids=executed, response_id=prev, commentary=commentary, usage=usage)


__all__ = [
    "RequestBuilder",
    "ToolCallResult",
    "ToolStepOutcome",
    "ProviderStep",
    "LoopResult",
    "SendFn",
    "ToolDebugCallback",
    "execute_tool_calls",
    "has_user_visible_text",
    "user_visible_text",
    "parse_tool_arguments",
    "run_tool_loop",
]
