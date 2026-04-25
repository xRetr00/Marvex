from packages.contracts import (
    FinalResponse,
    FinishReason,
    ProviderRequest,
    ResponseType,
    TraceLevel,
    TraceStage,
    TurnInput,
    TurnOutput,
)
from packages.ports.provider import ProviderPort
from packages.telemetry import NoopTelemetrySink, TelemetrySink, make_trace_event


class TurnOrchestrator:
    def __init__(
        self,
        provider: ProviderPort,
        model: str = "fake-model",
        instructions: str | None = None,
        provider_options: dict[str, object] | None = None,
        telemetry_sink: TelemetrySink | None = None,
    ) -> None:
        self._provider = provider
        self._model = model
        self._instructions = instructions
        self._provider_options = dict(provider_options or {})
        self._telemetry_sink = telemetry_sink or NoopTelemetrySink()

    def run_turn(self, turn_input: TurnInput) -> TurnOutput:
        self._emit(
            turn_input,
            TraceStage.TURN_RECEIVED,
            "Turn received.",
            {"source": turn_input.source.value},
        )
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
        self._emit(
            turn_input,
            TraceStage.PROVIDER_REQUEST_CREATED,
            "Provider request created.",
            {"model": provider_request.model},
        )
        self._emit(
            turn_input,
            TraceStage.PROVIDER_REQUEST_SENT,
            "Provider request sent.",
            {"model": provider_request.model},
        )
        try:
            provider_response = self._provider.send(provider_request)
        except Exception as exc:
            self._emit(
                turn_input,
                TraceStage.TURN_FAILED,
                "Turn failed.",
                {
                    "status": "exception",
                    "error_type": type(exc).__name__,
                    "error_message": str(exc),
                },
                level=TraceLevel.ERROR,
            )
            raise

        response_data = {"provider_name": provider_response.provider_name}
        if provider_response.error is not None:
            response_data.update(
                {
                    "status": "provider_error",
                    "error_code": provider_response.error.code.value,
                    "error_message": provider_response.error.message,
                }
            )
        self._emit(
            turn_input,
            TraceStage.PROVIDER_RESPONSE_RECEIVED,
            "Provider response received.",
            response_data,
            level=TraceLevel.ERROR if provider_response.error is not None else TraceLevel.INFO,
        )

        if provider_response.error is not None:
            final_response = FinalResponse(
                text=provider_response.error.message,
                response_type=ResponseType.ERROR,
                finish_reason=FinishReason.ERROR,
                safe_for_tts=False,
                metadata={"provider_name": provider_response.provider_name},
            )
            self._emit(
                turn_input,
                TraceStage.FINAL_RESPONSE_CREATED,
                "Final response created.",
                {"response_type": final_response.response_type.value},
            )
            self._emit(
                turn_input,
                TraceStage.TURN_COMPLETED,
                "Turn completed.",
                {
                    "status": "provider_error",
                    "error_code": provider_response.error.code.value,
                    "error_message": provider_response.error.message,
                },
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
        self._emit(
            turn_input,
            TraceStage.FINAL_RESPONSE_CREATED,
            "Final response created.",
            {"response_type": final_response.response_type.value},
        )
        self._emit(
            turn_input,
            TraceStage.TURN_COMPLETED,
            "Turn completed.",
            {"status": "success"},
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

    def _emit(
        self,
        turn_input: TurnInput,
        stage: TraceStage,
        message: str,
        data: dict[str, object],
        level: TraceLevel = TraceLevel.INFO,
    ) -> None:
        self._telemetry_sink.emit(
            make_trace_event(
                schema_version=turn_input.schema_version,
                trace_id=turn_input.trace_id,
                turn_id=turn_input.turn_id,
                stage=stage,
                level=level,
                message=message,
                data=data,
            )
        )
