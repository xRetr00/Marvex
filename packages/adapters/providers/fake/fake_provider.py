from dataclasses import dataclass
from enum import Enum

from packages.contracts import (
    ErrorCode,
    ErrorEnvelope,
    FinishReason,
    ProviderRequest,
    ProviderResponse,
)


class FakeProviderMode(str, Enum):
    SUCCESS = "success"
    ERROR = "error"


@dataclass(frozen=True)
class FakeProviderConfig:
    mode: FakeProviderMode = FakeProviderMode.SUCCESS
    output_text: str = "fake provider response"
    response_id: str | None = "fake-response-001"
    error_code: ErrorCode = ErrorCode.PROVIDER_ERROR
    error_message: str = "Fake provider configured error."


class FakeProvider:
    def __init__(self, config: FakeProviderConfig | None = None) -> None:
        self._config = config or FakeProviderConfig()

    def send(self, request: ProviderRequest) -> ProviderResponse:
        raw_metadata = {"previous_response_id": request.previous_response_id}
        if self._config.mode == FakeProviderMode.ERROR:
            return ProviderResponse(
                schema_version=request.schema_version,
                trace_id=request.trace_id,
                turn_id=request.turn_id,
                provider_name="fake",
                response_id=self._config.response_id,
                output_text="",
                finish_reason=FinishReason.ERROR,
                usage={},
                raw_metadata=raw_metadata,
                error=ErrorEnvelope(
                    schema_version=request.schema_version,
                    trace_id=request.trace_id,
                    error_id="fake-error-001",
                    code=self._config.error_code,
                    message=self._config.error_message,
                    recoverable=True,
                    source="fake_provider",
                    details={},
                ),
            )

        return ProviderResponse(
            schema_version=request.schema_version,
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            provider_name="fake",
            response_id=self._config.response_id,
            output_text=self._config.output_text,
            finish_reason=FinishReason.STOP,
            usage={},
            raw_metadata=raw_metadata,
            error=None,
        )
