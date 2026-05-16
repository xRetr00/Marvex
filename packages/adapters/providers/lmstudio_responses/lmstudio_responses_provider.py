from __future__ import annotations

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
        call_args = {
            "model": request.model,
            "input": request.input_text,
        }
        if request.instructions is not None:
            call_args["instructions"] = request.instructions
        if request.previous_response_id is not None:
            call_args["previous_response_id"] = request.previous_response_id

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
        for name, value in provider_options.items():
            if name in {"temperature", "max_output_tokens", "top_p", "timeout"}:
                allowed[name] = value
            else:
                ignored.append(name)
        return allowed, sorted(ignored)

    def _read_output_text(self, response: object) -> str:
        direct_output = self._read_attr(response, "output_text")
        if isinstance(direct_output, str):
            return direct_output

        parts: list[str] = []
        output = self._read_attr(response, "output")
        if not isinstance(output, list):
            return ""
        for item in output:
            content = self._read_attr(item, "content")
            if not isinstance(content, list):
                continue
            for content_item in content:
                content_type = self._read_attr(content_item, "type")
                text = self._read_attr(content_item, "text")
                if content_type == "output_text" and isinstance(text, str):
                    parts.append(text)
        return "".join(parts)

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
