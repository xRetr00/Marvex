from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import litellm
from pydantic import BaseModel

from packages.contracts import (
    ErrorCode,
    ErrorEnvelope,
    FinishReason,
    ProviderRequest,
    ProviderResponse,
)
from packages.provider_structured_output import map_adapter_raw_output_to_structured_result

from .conversation_store import LiteLLMConversationStore


@dataclass(frozen=True)
class LiteLLMProviderConfig:
    provider_name: str = "litellm"
    api_key: str | None = None
    base_url: str | None = None
    provider_mode: str = "litellm_sdk"
    timeout_seconds: float | None = None
    error_id: str = "litellm-error-001"


class LiteLLMProvider:
    """LiteLLM chat-completions adapter with optional client-side multi-turn."""

    def __init__(
        self,
        config: LiteLLMProviderConfig | None = None,
        *,
        conversation_store: LiteLLMConversationStore | None = None,
    ) -> None:
        self._config = config or LiteLLMProviderConfig()
        self._conversation_store = conversation_store

    def send(self, request: ProviderRequest) -> ProviderResponse:
        messages = self._build_messages(request)
        call_args = {
            "model": self._model_for_call(request.model),
            "messages": messages,
        }
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
        # Agentic tool-calling (docs/TODO/02): only send tools when the caller
        # supplied them. Absent tools, behavior is byte-for-byte the historical
        # path (no tools/tool_choice keys), preserving the no-tools invariant.
        if request.tools:
            call_args["tools"] = request.tools
        raw_metadata: dict[str, object] = {
            "previous_response_id": request.previous_response_id,
            "ignored_provider_options": ignored_options,
        }

        try:
            completion_response = litellm.completion(**call_args)
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

        response_id = self._read_attr(completion_response, "id")
        output_text = self._read_output_text(completion_response)
        tool_calls = self._read_tool_calls(completion_response)
        self._record_turn(response_id, messages, output_text)
        return ProviderResponse(
            schema_version=request.schema_version,
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            provider_name=self._config.provider_name,
            response_id=response_id,
            output_text=output_text,
            finish_reason=self._map_finish_reason(
                self._read_first_choice_attr(completion_response, "finish_reason")
            ),
            usage=self._to_plain_mapping(self._read_attr(completion_response, "usage")),
            raw_metadata=raw_metadata,
            error=None,
            tool_calls=tool_calls or None,
        )

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

    def _build_messages(self, request: ProviderRequest) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        prior: list[dict[str, Any]] = []
        if self._conversation_store is not None:
            prior = self._conversation_store.recall(request.previous_response_id)
        if prior:
            if request.instructions is not None:
                messages.append({"role": "system", "content": request.instructions})
                prior = [m for m in prior if m.get("role") != "system"]
            messages.extend(prior)
        elif request.instructions is not None:
            messages.append({"role": "system", "content": request.instructions})
        messages.append({"role": "user", "content": request.input_text})
        # Agentic continuation (docs/TODO/02): append prior assistant tool-call
        # turns + their tool-result messages so the model can continue after a
        # tool executed. These are already OpenAI-shaped by the caller.
        if request.tool_messages:
            messages.extend(request.tool_messages)
        return messages

    def _read_tool_calls(self, response: object) -> list[dict[str, Any]]:
        """Extract OpenAI-style tool calls from the first choice's message."""

        message = self._read_first_choice_attr(response, "message")
        raw_calls = self._read_attr(message, "tool_calls")
        if not isinstance(raw_calls, list):
            return []
        calls: list[dict[str, Any]] = []
        for raw in raw_calls:
            function = self._read_attr(raw, "function")
            name = self._read_attr(function, "name")
            arguments = self._read_attr(function, "arguments")
            call_id = self._read_attr(raw, "id")
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
        messages: list[dict[str, str]],
        output_text: str,
    ) -> None:
        if self._conversation_store is None:
            return
        if not isinstance(response_id, str) or not response_id.strip():
            return
        updated = list(messages)
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
                allowed["max_tokens"] = value
            elif name == "max_output_tokens":
                if "max_tokens" in provider_options:
                    ignored.append(name)
                else:
                    allowed["max_tokens"] = value
            elif name == "timeout":
                allowed["timeout"] = value
            else:
                ignored.append(name)

        return allowed, sorted(ignored)

    def _read_output_text(self, response: object) -> str:
        message = self._read_first_choice_attr(response, "message")
        content = self._read_attr(message, "content")
        return content if isinstance(content, str) else ""

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

    def _model_for_call(self, model: str) -> str:
        if (
            self._config.base_url
            and self._config.provider_mode in {"openai_compatible", "litellm_proxy"}
            and "/" not in model
        ):
            return f"openai/{model}"
        return model
