from __future__ import annotations

from collections.abc import Iterator, Sequence
from dataclasses import dataclass
from typing import Any, Callable

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
    StreamStarted,
    StreamTextDelta,
)
from packages.provider_structured_output import map_adapter_raw_output_to_structured_result


ClientFactory = Callable[..., object]


@dataclass(frozen=True)
class OpenRouterProviderConfig:
    provider_name: str = "openrouter"
    api_key: str | None = None
    timeout_seconds: float | None = None
    http_referer: str = "https://marvex.local"
    x_title: str = "Marvex"
    error_id: str = "openrouter-error-001"


class OpenRouterProvider:
    """OpenRouter Responses API adapter backed by the official Python SDK."""

    def __init__(
        self,
        config: OpenRouterProviderConfig | None = None,
        *,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._config = config or OpenRouterProviderConfig()
        self._client_factory = client_factory

    def send(self, request: ProviderRequest) -> ProviderResponse:
        call_args = self._build_call_args(request, stream=False)
        raw_metadata: dict[str, object] = {
            "previous_response_id": request.previous_response_id,
            "ignored_provider_options": call_args.pop("_ignored_provider_options"),
            "api_surface": "responses",
        }

        try:
            client = self._make_client()
            provider_response = self._materialize_response(
                self._read_attr(self._read_attr(client, "beta"), "responses").send(**call_args)
            )
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
                    source="openrouter_provider",
                    details={"exception_type": type(exc).__name__},
                ),
            )

        openrouter_metadata = self._read_attr(provider_response, "openrouter_metadata")
        if openrouter_metadata is not None:
            raw_metadata["openrouter_metadata"] = self._to_plain_mapping(openrouter_metadata)
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
        call_args = self._build_call_args(request, stream=True)
        call_args.pop("_ignored_provider_options", None)
        try:
            client = self._make_client()
            stream = self._read_attr(self._read_attr(client, "beta"), "responses").send(**call_args)
        except Exception as exc:
            yield StreamError(self._safe_exception_message(exc))
            return

        response_id: str | None = None
        final_text_parts: list[str] = []
        output_delta_keys: set[tuple[object, ...]] = set()
        try:
            for event in self._iter_response_events(stream):
                event_type = str(self._read_attr(event, "type") or "")
                if event_type.endswith("response.created") or event_type == "response.created":
                    response_obj = self._read_attr(event, "response")
                    created_id = self._read_optional_string(response_obj, "id") if response_obj is not None else None
                    if created_id:
                        response_id = created_id
                        yield StreamStarted(response_id=created_id)
                elif event_type.endswith("output_text.delta"):
                    delta = _event_text_delta(event)
                    if delta:
                        output_delta_keys.add(_event_part_key(event))
                        final_text_parts.append(delta)
                        yield StreamTextDelta(delta)
                elif event_type.endswith("output_text.done"):
                    text = _event_done_text(event)
                    if text and _event_part_key(event) not in output_delta_keys:
                        final_text_parts.append(text)
                        yield StreamTextDelta(text)
                elif event_type.endswith("response.completed") or event_type == "response.completed":
                    response_obj = self._read_attr(event, "response")
                    response_id = self._read_optional_string(response_obj, "id") if response_obj is not None else response_id
                    authoritative = self._read_output_text(response_obj) if response_obj is not None else ""
                    joined = "".join(final_text_parts)
                    yield StreamCompleted(
                        response_id=response_id,
                        finish_reason="stop",
                        output_text=authoritative if len(authoritative) >= len(joined) else joined,
                        usage=self._to_plain_mapping(self._read_attr(response_obj, "usage")),
                    )
                    return
                elif event_type.endswith("failed") or event_type.endswith("error"):
                    yield StreamError("provider stream reported a failure")
                    return
        except Exception as exc:
            yield StreamError(self._safe_exception_message(exc))
            return
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

    def _build_call_args(self, request: ProviderRequest, *, stream: bool) -> dict[str, Any]:
        tool_output_items = _responses_function_outputs(request.tool_messages)
        allowed_options, ignored_options = self._filter_provider_options(request.provider_options)
        call_args: dict[str, Any] = {
            "model": request.model,
            "input": tool_output_items if tool_output_items else request.input_text,
            "http_headers": {"X-OpenRouter-Metadata": "enabled"},
            "stream": stream,
            "_ignored_provider_options": ignored_options,
        }
        if request.instructions is not None:
            call_args["instructions"] = request.instructions
        if request.previous_response_id is not None:
            call_args["previous_response_id"] = request.previous_response_id
        if request.tools:
            call_args["tools"] = _responses_tool_schemas(request.tools)
        call_args.update(allowed_options)
        return call_args

    def _make_client(self) -> object:
        factory = self._client_factory or _openrouter_client_class()
        return factory(**self._client_kwargs())

    def _client_kwargs(self) -> dict[str, object]:
        kwargs: dict[str, object] = {
            "api_key": self._config.api_key,
            "http_referer": self._config.http_referer,
            "x_title": self._config.x_title,
        }
        if self._config.timeout_seconds is not None:
            kwargs["timeout_ms"] = int(self._config.timeout_seconds * 1000)
        return {key: value for key, value in kwargs.items() if value is not None}

    def _filter_provider_options(
        self, provider_options: dict[str, Any]
    ) -> tuple[dict[str, object], list[str]]:
        allowed: dict[str, object] = {}
        ignored: list[str] = []
        reasoning: dict[str, object] = {}
        passthrough = {
            "cache_control",
            "frequency_penalty",
            "include",
            "max_output_tokens",
            "max_tool_calls",
            "metadata",
            "modalities",
            "models",
            "parallel_tool_calls",
            "plugins",
            "presence_penalty",
            "prompt",
            "prompt_cache_key",
            "provider",
            "safety_identifier",
            "service_tier",
            "session_id",
            "stop_server_tools_when",
            "temperature",
            "text",
            "tool_choice",
            "top_k",
            "top_logprobs",
            "top_p",
            "trace",
            "truncation",
            "user",
        }
        for name, value in provider_options.items():
            if name in passthrough:
                allowed[name] = value
            elif name == "max_tokens":
                allowed["max_output_tokens"] = value
            elif name == "reasoning" and isinstance(value, dict):
                allowed["reasoning"] = dict(value)
            elif name == "reasoning_effort" and isinstance(value, str) and value.strip():
                effort = _normalize_responses_reasoning_effort(value)
                if effort:
                    reasoning["effort"] = effort
                else:
                    ignored.append(name)
            elif name == "reasoning_summary" and isinstance(value, str) and value.strip():
                reasoning["summary"] = value.strip()
            else:
                ignored.append(name)
        if reasoning and "reasoning" not in allowed:
            allowed["reasoning"] = reasoning
        return allowed, sorted(ignored)

    def _materialize_response(self, value: object) -> object:
        if _looks_like_response(value):
            return value
        last_response: object | None = None
        for event in self._iter_response_events(value):
            event_response = self._read_attr(event, "response")
            if event_response is not None:
                last_response = event_response
            event_type = str(self._read_attr(event, "type") or "")
            if event_type.endswith("response.completed") and event_response is not None:
                return event_response
        return last_response if last_response is not None else value

    def _iter_response_events(self, value: object) -> Iterator[object]:
        enter = getattr(value, "__enter__", None)
        exit_method = getattr(value, "__exit__", None)
        if callable(enter) and callable(exit_method):
            with value as event_stream:
                yield from _iter_plain(event_stream)
            return
        yield from _iter_plain(value)

    def _safe_exception_message(self, exc: Exception) -> str:
        message = str(exc)
        api_key = self._config.api_key
        if api_key:
            message = message.replace(api_key, "[REDACTED]")
        return message or type(exc).__name__

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


def _openrouter_client_class() -> type[object]:
    from openrouter import OpenRouter

    return OpenRouter


def _iter_plain(value: object) -> Iterator[object]:
    if isinstance(value, Iterator):
        yield from value
        return
    if _is_item_sequence(value):
        yield from value


def _looks_like_response(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, dict):
        return bool(value.get("id") or value.get("output_text") or value.get("output"))
    return any(hasattr(value, name) for name in ("id", "output_text", "output"))


def _normalize_responses_reasoning_effort(value: str) -> str:
    cleaned = str(value or "").strip().lower()
    aliases = {
        "off": "none",
        "on": "medium",
        "max": "xhigh",
    }
    cleaned = aliases.get(cleaned, cleaned)
    return cleaned if cleaned in {"none", "minimal", "low", "medium", "high", "xhigh"} else ""


def _event_text_delta(event: object) -> str:
    delta = getattr(event, "delta", "")
    if isinstance(delta, str):
        return delta
    if isinstance(delta, dict):
        text = delta.get("text")
        if isinstance(text, str):
            return text
    return ""


def _event_done_text(event: object) -> str:
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
    return (
        getattr(event, "item_id", None),
        getattr(event, "output_index", None),
        getattr(event, "content_index", None),
        getattr(event, "summary_index", None),
    )


def _is_item_sequence(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _responses_tool_schemas(tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
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
