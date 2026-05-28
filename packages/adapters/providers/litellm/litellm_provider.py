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
            "model": request.model,
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
                    details={"exception_type": type(exc).__name__},
                ),
            )

        response_id = self._read_attr(completion_response, "id")
        output_text = self._read_output_text(completion_response)
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

    def _build_messages(self, request: ProviderRequest) -> list[dict[str, str]]:
        messages: list[dict[str, str]] = []
        prior: list[dict[str, str]] = []
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
        return messages

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
