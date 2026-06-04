from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Callable

from openai import OpenAI
from pydantic import BaseModel

from packages.contracts import (
    ErrorCode,
    ErrorEnvelope,
    FinishReason,
    ProviderRequest,
    ProviderResponse,
)
from packages.contracts.streaming_models import (
    StreamCompleted,
    StreamError,
    StreamEvent,
    StreamTextDelta,
)
from packages.provider_structured_output import map_adapter_raw_output_to_structured_result


ClientFactory = Callable[..., object]


@dataclass(frozen=True)
class LMStudioResponsesProviderConfig:
    provider_name: str = "lmstudio_responses"
    base_url: str = "http://localhost:1234/v1"
    api_key: str = "lm-studio"
    timeout: float | None = None
    error_id: str = "lmstudio-responses-error-001"


class LMStudioResponsesProvider:
    def __init__(
        self,
        config: LMStudioResponsesProviderConfig | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._config = config or LMStudioResponsesProviderConfig()
        self._client_factory = client_factory or OpenAI

    def send(self, request: ProviderRequest) -> ProviderResponse:
        call_args: dict[str, Any] = {
            "model": request.model,
        }
        # Agentic continuation (docs/TODO/02): when tool results are threaded
        # back, the Responses API takes `input` as a list of function_call_output
        # items referencing the prior (stored) response via previous_response_id.
        # Otherwise `input` is the plain user text, exactly as before.
        tool_output_items = _responses_function_outputs(request.tool_messages)
        if tool_output_items:
            call_args["input"] = tool_output_items
        else:
            call_args["input"] = request.input_text
        if request.instructions is not None:
            call_args["instructions"] = request.instructions
        if request.previous_response_id is not None:
            call_args["previous_response_id"] = request.previous_response_id
        # Tool schemas only when provided; absent tools => byte-for-byte the
        # historical no-tools request (no tools/tool_choice keys).
        if request.tools:
            call_args["tools"] = _responses_tool_schemas(request.tools)

        allowed_options, ignored_options = self._filter_provider_options(
            request.provider_options
        )
        call_args.update(allowed_options)
        raw_metadata: dict[str, object] = {
            "previous_response_id": request.previous_response_id,
            "ignored_provider_options": ignored_options,
        }

        try:
            client = self._client_factory(**self._client_kwargs())
            provider_response = self._read_attr(client, "responses").create(**call_args)
        except Exception as exc:
            return ProviderResponse(
                schema_version=request.schema_version,
                trace_id=request.trace_id,
                turn_id=request.turn_id,
                provider_name=self._config.provider_name,
                response_id=None,
                output_text="",
                finish_reason=FinishReason.ERROR,
                usage={},
                raw_metadata=raw_metadata,
                error=ErrorEnvelope(
                    schema_version=request.schema_version,
                    trace_id=request.trace_id,
                    error_id=self._config.error_id,
                    code=ErrorCode.PROVIDER_ERROR,
                    message=self._safe_exception_message(exc),
                    recoverable=True,
                    source="lmstudio_responses_provider",
                    details={"exception_type": type(exc).__name__},
                ),
            )

        tool_calls = self._read_tool_calls(provider_response)
        return ProviderResponse(
            schema_version=request.schema_version,
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            provider_name=self._config.provider_name,
            response_id=self._read_optional_string(provider_response, "id"),
            output_text=self._read_output_text(provider_response),
            finish_reason=self._map_finish_reason(provider_response),
            usage=self._to_plain_mapping(self._read_attr(provider_response, "usage")),
            raw_metadata=raw_metadata,
            error=None,
            tool_calls=tool_calls or None,
        )

    def stream_send(self, request: ProviderRequest):
        """Yield streaming events for a turn (docs/TODO/06).

        Additive and opt-in: ``send`` is byte-for-byte unchanged. This issues a
        Responses-API streaming call (``stream=True``) and yields
        StreamTextDelta for each text chunk, then a terminal StreamCompleted (or
        StreamError on failure, so the caller falls back to non-streaming).
        """

        call_args: dict[str, Any] = {"model": request.model, "stream": True}
        tool_output_items = _responses_function_outputs(request.tool_messages)
        call_args["input"] = tool_output_items if tool_output_items else request.input_text
        if request.instructions is not None:
            call_args["instructions"] = request.instructions
        if request.previous_response_id is not None:
            call_args["previous_response_id"] = request.previous_response_id
        if request.tools:
            call_args["tools"] = _responses_tool_schemas(request.tools)
        allowed_options, _ignored = self._filter_provider_options(request.provider_options)
        call_args.update(allowed_options)

        try:
            client = self._client_factory(**self._client_kwargs())
            stream = self._read_attr(client, "responses").create(**call_args)
        except Exception as exc:
            yield StreamError(self._safe_exception_message(exc))
            return

        response_id: str | None = None
        final_text_parts: list[str] = []
        # LM Studio exposes model reasoning as Responses-style reasoning_text
        # deltas. Keep it inside the existing <think> channel so the shell can
        # render/collapse it and strip it from speech/copy paths.
        reasoning_open = False
        output_delta_keys: set[tuple[object, ...]] = set()
        reasoning_delta_keys: set[tuple[object, ...]] = set()
        try:
            for event in stream:
                event_type = str(getattr(event, "type", "") or "")
                if _is_reasoning_delta(event_type):
                    delta = _event_text_delta(event)
                    if delta:
                        reasoning_delta_keys.add(_event_part_key(event))
                        if not reasoning_open:
                            reasoning_open = True
                            final_text_parts.append("<think>")
                            yield StreamTextDelta("<think>")
                        final_text_parts.append(delta)
                        yield StreamTextDelta(delta)
                elif _is_reasoning_done(event_type):
                    text = _event_done_text(event)
                    if text and _event_part_key(event) not in reasoning_delta_keys:
                        if not reasoning_open:
                            reasoning_open = True
                            final_text_parts.append("<think>")
                            yield StreamTextDelta("<think>")
                        final_text_parts.append(text)
                        yield StreamTextDelta(text)
                elif event_type.endswith("output_text.delta"):
                    delta = _event_text_delta(event)
                    if delta:
                        output_delta_keys.add(_event_part_key(event))
                        if reasoning_open:
                            reasoning_open = False
                            final_text_parts.append("</think>")
                            yield StreamTextDelta("</think>")
                        final_text_parts.append(delta)
                        yield StreamTextDelta(delta)
                elif event_type.endswith("output_text.done"):
                    text = _event_done_text(event)
                    if text and _event_part_key(event) not in output_delta_keys:
                        if reasoning_open:
                            reasoning_open = False
                            final_text_parts.append("</think>")
                            yield StreamTextDelta("</think>")
                        final_text_parts.append(text)
                        yield StreamTextDelta(text)
                elif event_type.endswith("response.completed") or event_type == "response.completed":
                    if reasoning_open:
                        reasoning_open = False
                        final_text_parts.append("</think>")
                        yield StreamTextDelta("</think>")
                    response_obj = getattr(event, "response", None)
                    response_id = self._read_optional_string(response_obj, "id") if response_obj is not None else response_id
                    authoritative = self._read_output_text(response_obj) if response_obj is not None else ""
                    tool_calls = self._read_tool_calls(response_obj) if response_obj is not None else []
                    # The accumulated stream (with the <think> block) is the
                    # authoritative full text whenever it is at least as long as
                    # the provider's message-only output_text, so reasoning is
                    # never dropped from the persisted turn.
                    joined = "".join(final_text_parts)
                    output_text = joined if len(joined) >= len(authoritative) else authoritative
                    yield StreamCompleted(
                        response_id=response_id,
                        finish_reason="stop",
                        output_text=output_text,
                        tool_calls=tool_calls or None,
                        usage=self._to_plain_mapping(self._read_attr(response_obj, "usage")),
                    )
                    return
                elif event_type.endswith("failed") or event_type.endswith("error"):
                    yield StreamError("provider stream reported a failure")
                    return
        except Exception as exc:
            yield StreamError(self._safe_exception_message(exc))
            return
        # Stream ended without an explicit completed event.
        if reasoning_open:
            final_text_parts.append("</think>")
            yield StreamTextDelta("</think>")
        yield StreamCompleted(response_id=response_id, finish_reason="stop", output_text="".join(final_text_parts))

    def map_raw_output_to_structured_result(
        self,
        *,
        request: ProviderRequest,
        raw_output_text: str,
        target_contract: str,
        target_model: type[BaseModel],
        include_raw_preview: bool = False,
    ) -> object:
        return map_adapter_raw_output_to_structured_result(
            schema_version=request.schema_version,
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            target_contract=target_contract,
            raw_output_text=raw_output_text,
            target_model=target_model,
            include_raw_preview=include_raw_preview,
        )

    def _client_kwargs(self) -> dict[str, object]:
        kwargs: dict[str, object] = {
            "base_url": self._config.base_url,
            "api_key": self._config.api_key,
        }
        if self._config.timeout is not None:
            kwargs["timeout"] = self._config.timeout
        return kwargs

    def _safe_exception_message(self, exc: Exception) -> str:
        message = str(exc)
        api_key = self._config.api_key
        if api_key:
            message = message.replace(api_key, "[REDACTED]")
        return message

    def _filter_provider_options(
        self, provider_options: dict[str, Any]
    ) -> tuple[dict[str, object], list[str]]:
        allowed: dict[str, object] = {}
        ignored: list[str] = []
        reasoning: dict[str, object] = {}
        for name, value in provider_options.items():
            if name in {"temperature", "max_output_tokens", "top_p", "timeout", "parallel_tool_calls"}:
                allowed[name] = value
            elif name == "reasoning_effort" and isinstance(value, str) and value.strip():
                reasoning["effort"] = value.strip()
            elif name == "reasoning_summary" and isinstance(value, str) and value.strip():
                reasoning["summary"] = value.strip()
            else:
                ignored.append(name)
        if reasoning:
            allowed["reasoning"] = reasoning
        return allowed, sorted(ignored)

    def _read_output_text(self, response: object) -> str:
        direct_output = self._read_attr(response, "output_text")
        if isinstance(direct_output, str):
            return direct_output

        parts: list[str] = []
        output = self._read_attr(response, "output")
        if not _is_item_sequence(output):
            return ""
        for item in output:
            content = self._read_attr(item, "content")
            if not _is_item_sequence(content):
                continue
            for content_item in content:
                content_type = self._read_attr(content_item, "type")
                text = self._read_attr(content_item, "text")
                if content_type == "output_text" and isinstance(text, str):
                    parts.append(text)
        return "".join(parts)

    def _read_tool_calls(self, response: object) -> list[dict[str, Any]]:
        """Extract Responses-API function_call items into engine-shaped calls.

        The Responses API returns tool calls as ``output`` items of type
        ``function_call`` with ``name`` / ``arguments`` / ``call_id``. We
        normalise them into the same ``{"id", "function": {"name",
        "arguments"}}`` shape the agentic engine consumes for both providers.
        """

        output = self._read_attr(response, "output")
        if not _is_item_sequence(output):
            return []
        calls: list[dict[str, Any]] = []
        for item in output:
            if self._read_attr(item, "type") != "function_call":
                continue
            name = self._read_attr(item, "name")
            if not isinstance(name, str) or not name.strip():
                continue
            arguments = self._read_attr(item, "arguments")
            call_id = self._read_attr(item, "call_id") or self._read_attr(item, "id")
            calls.append(
                {
                    "id": str(call_id) if isinstance(call_id, str) and call_id else f"call_{len(calls)}",
                    "type": "function",
                    "function": {
                        "name": name,
                        "arguments": arguments if isinstance(arguments, str) else "{}",
                    },
                }
            )
        return calls

    def _read_optional_string(self, value: object, name: str) -> str | None:
        candidate = self._read_attr(value, name)
        return candidate if isinstance(candidate, str) else None

    def _read_attr(self, value: object, name: str) -> object:
        if isinstance(value, dict):
            return value.get(name)
        return getattr(value, name, None)

    def _to_plain_mapping(self, value: object) -> dict[str, Any]:
        if value is None:
            return {}
        if isinstance(value, dict):
            return dict(value)
        if hasattr(value, "model_dump"):
            dumped = value.model_dump()
            return dumped if isinstance(dumped, dict) else {}
        if hasattr(value, "dict"):
            dumped = value.dict()
            return dumped if isinstance(dumped, dict) else {}
        if hasattr(value, "__dict__"):
            return dict(value.__dict__)
        return {}

    def _map_finish_reason(self, response: object) -> FinishReason:
        value = self._read_attr(response, "finish_reason")
        if value is None:
            value = self._read_attr(response, "status")
        if value in {"stop", "completed"}:
            return FinishReason.STOP
        if value in {"length", "incomplete"}:
            return FinishReason.LENGTH
        if value in {"cancelled", "canceled"}:
            return FinishReason.CANCELLED
        if value in {"error", "failed"}:
            return FinishReason.ERROR
        return FinishReason.UNKNOWN


def _is_reasoning_delta(event_type: str) -> bool:
    """True for provider-generated reasoning deltas."""

    return (
        ("reasoning_summary" in event_type or "reasoning_text" in event_type)
        and event_type.endswith(".delta")
    )


def _is_reasoning_done(event_type: str) -> bool:
    """True for completed reasoning text events used when deltas are absent."""

    return (
        ("reasoning_summary_text" in event_type or "reasoning_text" in event_type)
        and event_type.endswith(".done")
    )


def _event_text_delta(event: object) -> str:
    """Read the incremental text from a Responses streaming delta event."""

    delta = getattr(event, "delta", "")
    if isinstance(delta, str):
        return delta
    # Some SDK builds wrap the chunk as {"text": "..."} on the delta attribute.
    if isinstance(delta, dict):
        text = delta.get("text")
        if isinstance(text, str):
            return text
    return ""


def _event_done_text(event: object) -> str:
    """Read finalized text from a Responses ``*.done`` event."""

    text = getattr(event, "text", "")
    if isinstance(text, str):
        return text
    part = getattr(event, "part", None)
    if isinstance(part, dict):
        nested = part.get("text")
        return nested if isinstance(nested, str) else ""
    nested = getattr(part, "text", "")
    return nested if isinstance(nested, str) else ""


def _event_part_key(event: object) -> tuple[object, ...]:
    """Stable key for matching delta/done events for one content part."""

    return (
        getattr(event, "item_id", None),
        getattr(event, "output_index", None),
        getattr(event, "content_index", None),
        getattr(event, "summary_index", None),
    )


def _is_item_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _responses_tool_schemas(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert chat-completions tool schemas to the flatter Responses-API shape.

    Registry tool_schemas() emits ``{"type":"function","function":{name,
    description,parameters}}``; the Responses API expects the function fields
    at the top level: ``{"type":"function","name",...,"parameters":...}``.
    Tools already in the flat shape pass through unchanged.
    """

    converted: list[dict[str, Any]] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        fn = tool.get("function")
        if isinstance(fn, dict):
            converted.append(
                {
                    "type": "function",
                    "name": fn.get("name"),
                    "description": fn.get("description", ""),
                    "parameters": fn.get("parameters", {"type": "object"}),
                }
            )
        else:
            converted.append(tool)
    return converted


def _responses_function_outputs(tool_messages: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
    """Translate threaded tool-result messages into Responses input items.

    The agentic engine emits OpenAI chat-style tool messages
    ({"role":"tool","tool_call_id":X,"content":Y}). The Responses API takes
    these as ``input`` items of type ``function_call_output`` referencing the
    prior (stored) response via previous_response_id. The assistant tool_calls
    echo message is not needed as input here (the model already emitted it).
    """

    if not tool_messages:
        return []
    items: list[dict[str, Any]] = []
    for message in tool_messages:
        if not isinstance(message, dict) or message.get("role") != "tool":
            continue
        call_id = message.get("tool_call_id")
        content = message.get("content")
        if not isinstance(call_id, str) or not call_id:
            continue
        items.append(
            {
                "type": "function_call_output",
                "call_id": call_id,
                "output": content if isinstance(content, str) else "",
            }
        )
    return items
