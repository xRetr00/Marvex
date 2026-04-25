from typing import Protocol

from packages.contracts import (
    FinalResponse,
    FinishReason,
    ProviderRequest,
    ProviderResponse,
    ResponseType,
    TurnInput,
    TurnOutput,
)


class ProviderDependency(Protocol):
    def send(self, request: ProviderRequest) -> ProviderResponse:
        ...


class TurnOrchestrator:
    def __init__(
        self,
        provider: ProviderDependency,
        model: str = "fake-model",
        instructions: str | None = None,
        provider_options: dict[str, object] | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._instructions = instructions
        self._provider_options = dict(provider_options or {})

    def run_turn(self, turn_input: TurnInput) -> TurnOutput:
        provider_request = ProviderRequest(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            model=self._model,
            input_text=turn_input.input_text,
            instructions=self._instructions,
            previous_response_id=turn_input.previous_response_id,
            provider_options=dict(self._provider_options),
        )
        provider_response = self._provider.send(provider_request)

        if provider_response.error is not None:
            final_response = FinalResponse(
                text=provider_response.error.message,
                response_type=ResponseType.ERROR,
                finish_reason=FinishReason.ERROR,
                safe_for_tts=False,
                metadata={"provider_name": provider_response.provider_name},
            )
            return TurnOutput(
                schema_version=turn_input.schema_version,
                trace_id=turn_input.trace_id,
                turn_id=turn_input.turn_id,
                final_response=final_response,
                provider_response_id=provider_response.response_id,
                events=[],
                error=provider_response.error,
            )

        final_response = FinalResponse(
            text=provider_response.output_text,
            response_type=ResponseType.TEXT,
            finish_reason=provider_response.finish_reason,
            safe_for_tts=True,
            metadata={"provider_name": provider_response.provider_name},
        )
        return TurnOutput(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            final_response=final_response,
            provider_response_id=provider_response.response_id,
            events=[],
            error=None,
        )
