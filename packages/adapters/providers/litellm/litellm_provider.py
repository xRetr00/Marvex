from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Callable

os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import litellm
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
    StreamTextDelta,
)
from packages.provider_structured_output import map_adapter_raw_output_to_structured_result

from .conversation_store import LiteLLMConversationStore


ClientFactory = Callable[..., object]


@dataclass(frozen=True)
class LiteLLMProviderConfig:
    provider_name: str = "litellm"
    api_key: str | None = None
    base_url: str | None = None
    provider_mode: str = "litellm_sdk"
    timeout_seconds: float | None = None
    error_id: str = "litellm-error-001"


class LiteLLMProvider:
    """LiteLLM Responses API adapter."""

    def __init__(
        self,
        config: LiteLLMProviderConfig | None = None,
        *,
        conversation_store: LiteLLMConversationStore | None = None,
        client_factory: ClientFactory | None = None,
    ) -> None:
        self._config = config or LiteLLMProviderConfig()
        self._conversation_store = conversation_store
        self._client_factory = client_factory or OpenAI

    def send(self, request: ProviderRequest) -> ProviderResponse:
        if self._proxy_mode():
            return self._send_via_openai_responses(request)

        call_args = {
            "model": self._model_for_call(request.model),
            "input": self._build_responses_input(request),
        }
        if request.instructions is not None:
            call_args["instructions"] = request.instructions
        if request.previous_response_id is not None:
            call_args["previous_response_id"] = request.previous_response_id
        allowed_options, ignored_options = self._filter_provider_options(
            request.provider_options
        )
        if self._config.base_url is not None:
            call_args["api_base"] = self._config.base_url
        if self._config.api_key is not None:
            call_args["api_key"] = self._config.api_key
        if self._config.timeout_seconds is not None:
            call_args["timeout"] = self._config.timeout_seconds
        call_args.update(allowed_options)
        if request.tools:
            call_args["tools"] = self._responses_tools(request.tools)
        raw_metadata: dict[str, object] = {
            "previous_response_id": request.previous_response_id,
            "ignored_provider_options": ignored_options,
            "api_surface": "responses",
        }

        try:
            provider_response = litellm.responses(**call_args)
        except Exception as exc:
            message = str(exc)
            if self._config.api_key:
                message = message.replace(self._config.api_key, "[REDACTED]")
            details: dict[str, object] = {"exception_type": type(exc).__name__}
            lowered = message.lower()
            if (
                self._config.api_key is None
                and (
                    "api_key" in lowered
                    or "api key" in lowered
                    or "authentication" in lowered
                    or "401" in lowered
                    or "unauthorized" in lowered
                )
            ):
                # Most common first-run failure: no provider key configured.
                # Make that obvious in the trace dump instead of forcing the
                # operator to grep the raw exception message.
                model_prefix = request.model.split("/", 1)[0] if request.model else ""
                env_hint = {
                    "openrouter": "OPENROUTER_API_KEY",
                    "anthropic": "ANTHROPIC_API_KEY",
                    "openai": "OPENAI_API_KEY",
                    "groq": "GROQ_API_KEY",
                    "mistral": "MISTRAL_API_KEY",
                    "deepseek": "DEEPSEEK_API_KEY",
                    "together_ai": "TOGETHER_API_KEY",
                }.get(model_prefix)
                details["missing_api_key_hint"] = (
                    f"set {env_hint}" if env_hint else "configure a provider api key"
                )
                if env_hint:
                    message = (
                        f"Provider authentication failed. Set {env_hint} "
                        f"or configure the {model_prefix} provider via the control "
                        f"plane. Original: {message}"
                    )
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
                    message=message,
                    recoverable=True,
                    source="litellm_provider",
                    details=details,
                ),
            )

        response_id = self._read_attr(provider_response, "id")
        output_text = self._read_output_text(provider_response)
        tool_calls = self._read_tool_calls(provider_response)
        self._record_turn(response_id, request, output_text)
        return ProviderResponse(
            schema_version=request.schema_version,
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            provider_name=self._config.provider_name,
            response_id=response_id,
            output_text=output_text,
            finish_reason=self._map_responses_finish_reason(provider_response),
            usage=self._to_plain_mapping(self._read_attr(provider_response, "usage")),
            raw_metadata=raw_metadata,
            error=None,
            tool_calls=tool_calls or None,
        )

    def stream_send(self, request: ProviderRequest):
        """Yield streaming events for a turn (docs/TODO/06).

        Additive and opt-in. This issues a Responses API streaming call and
        yields StreamTextDelta for each content chunk, then a terminal
        StreamCompleted (or StreamError on failure, so the caller falls back to
        non-streaming).
        """

        if self._proxy_mode():
            yield from self._stream_via_openai_responses(request)
            return

        call_args: dict[str, Any] = {
            "model": self._model_for_call(request.model),
            "input": self._build_responses_input(request),
            "stream": True,
        }
        if request.instructions is not None:
            call_args["instructions"] = request.instructions
        if request.previous_response_id is not None:
            call_args["previous_response_id"] = request.previous_response_id
        allowed_options, _ignored = self._filter_provider_options(request.provider_options)
        if self._config.base_url is not None:
            call_args["api_base"] = self._config.base_url
        if self._config.api_key is not None:
            call_args["api_key"] = self._config.api_key
        if self._config.timeout_seconds is not None:
            call_args["timeout"] = self._config.timeout_seconds
        call_args.update(allowed_options)
        if request.tools:
            call_args["tools"] = self._responses_tools(request.tools)

        try:
            stream = litellm.responses(**call_args)
        except Exception as exc:
            yield StreamError(self._safe_exception_message(exc))
            return

        response_id: str | None = None
        finish_reason = "stop"
        final_text_parts: list[str] = []
        completed_response: object | None = None
        try:
            for event in stream:
                response_obj = self._read_attr(event, "response")
                chunk_id = self._read_attr(event, "id") or self._read_attr(response_obj, "id")
                if isinstance(chunk_id, str) and chunk_id:
                    response_id = chunk_id
                content = self._read_attr(event, "delta") or self._read_attr(event, "text")
                if isinstance(content, str) and content:
                    final_text_parts.append(content)
                    yield StreamTextDelta(content)
                event_type = self._read_attr(event, "type")
                if event_type == "response.incomplete":
                    finish_reason = "length"
                elif event_type == "response.failed":
                    finish_reason = "error"
                # Capture the authoritative completed response so streaming can
                # surface model-authored tool calls (drop-in for ``send``).
                if response_obj is not None and (
                    event_type is None or str(event_type).endswith("completed")
                ):
                    completed_response = response_obj
        except Exception as exc:
            yield StreamError(self._safe_exception_message(exc))
            return

        output_text = "".join(final_text_parts)
        tool_calls = self._read_tool_calls(completed_response) if completed_response is not None else []
        self._record_turn(response_id, request, output_text)
        yield StreamCompleted(
            response_id=response_id,
            finish_reason=finish_reason,
            output_text=output_text,
            tool_calls=tool_calls or None,
        )

    def _send_via_openai_responses(self, request: ProviderRequest) -> ProviderResponse:
        call_args = self._openai_responses_call_args(request, stream=False)
        allowed_options, ignored_options = self._filter_provider_options(request.provider_options)
        call_args.update(allowed_options)
        raw_metadata: dict[str, object] = {
            "previous_response_id": request.previous_response_id,
            "ignored_provider_options": ignored_options,
            "api_surface": "responses",
            "provider_mode": "litellm_proxy",
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
                    source="litellm_provider",
                    details={"exception_type": type(exc).__name__},
                ),
            )

        response_id = self._read_attr(provider_response, "id")
        output_text = self._read_output_text(provider_response)
        tool_calls = self._read_tool_calls(provider_response)
        self._record_turn(response_id, request, output_text)
        return ProviderResponse(
            schema_version=request.schema_version,
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            provider_name=self._config.provider_name,
            response_id=response_id if isinstance(response_id, str) else None,
            output_text=output_text,
            finish_reason=self._map_responses_finish_reason(provider_response),
            usage=self._to_plain_mapping(self._read_attr(provider_response, "usage")),
            raw_metadata=raw_metadata,
            error=None,
            tool_calls=tool_calls or None,
        )

    def _stream_via_openai_responses(self, request: ProviderRequest):
        call_args = self._openai_responses_call_args(request, stream=True)
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
        try:
            for event in stream:
                response_obj = self._read_attr(event, "response")
                chunk_id = self._read_attr(event, "id") or self._read_attr(response_obj, "id")
                if isinstance(chunk_id, str) and chunk_id:
                    response_id = chunk_id
                content = self._read_attr(event, "delta") or self._read_attr(event, "text")
                if isinstance(content, str) and content:
                    final_text_parts.append(content)
                    yield StreamTextDelta(content)
                event_type = str(self._read_attr(event, "type") or "")
                if event_type.endswith("response.completed") or event_type == "response.completed":
                    if response_obj is not None:
                        response_id = response_id or self._read_attr(response_obj, "id")
                        authoritative = self._read_output_text(response_obj)
                        tool_calls = self._read_tool_calls(response_obj)
                    else:
                        authoritative = ""
                        tool_calls = []
                    output_text = authoritative or "".join(final_text_parts)
                    self._record_turn(response_id, request, output_text)
                    yield StreamCompleted(
                        response_id=response_id if isinstance(response_id, str) else None,
                        finish_reason="stop",
                        output_text=output_text,
                        tool_calls=tool_calls or None,
                    )
                    return
                if event_type.endswith("failed") or event_type.endswith("error"):
                    yield StreamError("provider stream reported a failure")
                    return
        except Exception as exc:
            yield StreamError(self._safe_exception_message(exc))
            return
        output_text = "".join(final_text_parts)
        self._record_turn(response_id, request, output_text)
        yield StreamCompleted(response_id=response_id, finish_reason="stop", output_text=output_text)

    def _openai_responses_call_args(self, request: ProviderRequest, *, stream: bool) -> dict[str, Any]:
        call_args: dict[str, Any] = {
            "model": request.model,
            "input": self._build_responses_input(request),
        }
        if stream:
            call_args["stream"] = True
        if request.instructions is not None:
            call_args["instructions"] = request.instructions
        if request.previous_response_id is not None:
            call_args["previous_response_id"] = request.previous_response_id
        if request.tools:
            call_args["tools"] = self._responses_tools(request.tools)
        return call_args

    def _client_kwargs(self) -> dict[str, object]:
        kwargs: dict[str, object] = {
            "base_url": self._config.base_url,
            "api_key": self._config.api_key or "litellm",
        }
        if self._config.timeout_seconds is not None:
            kwargs["timeout"] = self._config.timeout_seconds
        return {key: value for key, value in kwargs.items() if value is not None}

    def _proxy_mode(self) -> bool:
        return self._config.provider_mode == "litellm_proxy"

    def _safe_exception_message(self, exc: Exception) -> str:
        message = str(exc)
        if self._config.api_key:
            message = message.replace(self._config.api_key, "[REDACTED]")
        return message or type(exc).__name__

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

    def _build_responses_input(self, request: ProviderRequest) -> str | list[dict[str, Any]]:
        if not request.tool_messages:
            return request.input_text
        items: list[dict[str, Any]] = []
        for message in request.tool_messages:
            if message.get("role") != "tool":
                continue
            call_id = message.get("tool_call_id")
            content = message.get("content")
            if not isinstance(call_id, str) or not call_id.strip():
                continue
            items.append(
                {
                    "type": "function_call_output",
                    "call_id": call_id.strip(),
                    "output": content if isinstance(content, str) else "",
                }
            )
        return items or request.input_text

    def _responses_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        converted: list[dict[str, Any]] = []
        for tool in tools:
            if tool.get("type") != "function":
                converted.append(dict(tool))
                continue
            function = tool.get("function")
            if not isinstance(function, dict):
                continue
            name = function.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            converted.append(
                {
                    "type": "function",
                    "name": name,
                    "description": function.get("description") if isinstance(function.get("description"), str) else "",
                    "parameters": function.get("parameters") if isinstance(function.get("parameters"), dict) else {"type": "object"},
                }
            )
        return converted

    def _read_tool_calls(self, response: object) -> list[dict[str, Any]]:
        """Extract OpenAI-style tool calls from Responses API output items."""

        raw_calls = [
            item
            for item in self._read_output_items(response)
            if self._read_attr(item, "type") == "function_call"
        ]
        if not isinstance(raw_calls, list):
            return []
        calls: list[dict[str, Any]] = []
        for raw in raw_calls:
            name = self._read_attr(raw, "name")
            arguments = self._read_attr(raw, "arguments")
            call_id = self._read_attr(raw, "call_id") or self._read_attr(raw, "id")
            if not isinstance(name, str) or not name.strip():
                continue
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

    def _record_turn(
        self,
        response_id: object,
        request: ProviderRequest,
        output_text: str,
    ) -> None:
        if self._conversation_store is None:
            return
        if not isinstance(response_id, str) or not response_id.strip():
            return
        updated: list[dict[str, str]] = []
        if request.instructions:
            updated.append({"role": "system", "content": request.instructions})
        updated.append({"role": "user", "content": request.input_text})
        if output_text:
            updated.append({"role": "assistant", "content": output_text})
        self._conversation_store.remember(response_id, updated)

    def _filter_provider_options(
        self, provider_options: dict[str, Any]
    ) -> tuple[dict[str, object], list[str]]:
        allowed: dict[str, object] = {}
        ignored: list[str] = []
        for name, value in provider_options.items():
            if name == "temperature":
                allowed["temperature"] = value
            elif name == "max_tokens":
                allowed["max_output_tokens"] = value
            elif name == "max_output_tokens":
                allowed["max_output_tokens"] = value
            elif name == "timeout":
                allowed["timeout"] = value
            else:
                ignored.append(name)

        return allowed, sorted(ignored)

    def _read_output_text(self, response: object) -> str:
        direct = self._read_attr(response, "output_text")
        if isinstance(direct, str):
            return direct
        parts: list[str] = []
        for item in self._read_output_items(response):
            if self._read_attr(item, "type") != "message":
                continue
            content = self._read_attr(item, "content")
            if isinstance(content, str):
                parts.append(content)
                continue
            if not isinstance(content, list):
                continue
            for part in content:
                text = self._read_attr(part, "text")
                if isinstance(text, str):
                    parts.append(text)
        return "".join(parts)

    def _read_output_items(self, response: object) -> list[object]:
        output = self._read_attr(response, "output")
        return output if isinstance(output, list) else []

    def _read_first_choice_attr(self, response: object, name: str) -> object:
        choices = self._read_attr(response, "choices")
        if not isinstance(choices, list) or not choices:
            return None
        return self._read_attr(choices[0], name)

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

    def _map_finish_reason(self, value: object) -> FinishReason:
        if value == "stop":
            return FinishReason.STOP
        if value == "length":
            return FinishReason.LENGTH
        if value in {"error", "content_filter"}:
            return FinishReason.ERROR
        return FinishReason.UNKNOWN

    def _map_responses_finish_reason(self, response: object) -> FinishReason:
        status = self._read_attr(response, "status")
        if status in {"completed", "stop"}:
            return FinishReason.STOP
        if status in {"incomplete", "length"}:
            return FinishReason.LENGTH
        if status in {"failed", "error", "cancelled"}:
            return FinishReason.ERROR if status != "cancelled" else FinishReason.CANCELLED
        return self._map_finish_reason(status)

    def _model_for_call(self, model: str) -> str:
        if (
            self._config.base_url
            and self._config.provider_mode in {"openai_compatible"}
            and "/" not in model
        ):
            return f"openai/{model}"
        return model
