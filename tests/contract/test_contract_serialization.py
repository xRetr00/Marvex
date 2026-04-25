from datetime import UTC, datetime

from packages.contracts import (
    ErrorCode,
    ErrorEnvelope,
    FinalResponse,
    FinishReason,
    HealthCheck,
    HealthStatus,
    ProviderRequest,
    ProviderResponse,
    ResponseType,
    Source,
    TraceEvent,
    TraceLevel,
    TraceStage,
    TurnInput,
    TurnOutput,
    VersionInfo,
)


def test_contracts_round_trip_through_json():
    final_response = FinalResponse(
        text="Hello.",
        response_type=ResponseType.TEXT,
        finish_reason=FinishReason.STOP,
        safe_for_tts=True,
        metadata={},
    )
    trace_event = TraceEvent(
        schema_version="0.1-draft",
        trace_id="trace-001",
        event_id="event-001",
        timestamp=datetime(2026, 4, 24, 12, 0, tzinfo=UTC),
        stage=TraceStage.TURN_COMPLETED,
        level=TraceLevel.INFO,
        message="Turn completed.",
        data={},
    )
    error = ErrorEnvelope(
        schema_version="0.1-draft",
        trace_id="trace-001",
        error_id="error-001",
        code=ErrorCode.VALIDATION_ERROR,
        message="Invalid input.",
        recoverable=True,
        source="contracts",
        details={},
    )

    examples = [
        TurnInput(
            schema_version="0.1-draft",
            trace_id="trace-001",
            turn_id="turn-001",
            input_text="Hello",
            previous_response_id="resp-previous",
            source=Source.CLI,
            metadata={},
        ),
        final_response,
        TurnOutput(
            schema_version="0.1-draft",
            trace_id="trace-001",
            turn_id="turn-001",
            final_response=final_response,
            provider_response_id="resp-001",
            events=[trace_event],
            error=None,
        ),
        ProviderRequest(
            schema_version="0.1-draft",
            trace_id="trace-001",
            turn_id="turn-001",
            model="local-model",
            input_text="Hello",
            instructions=None,
            previous_response_id=None,
            provider_options={},
        ),
        ProviderResponse(
            schema_version="0.1-draft",
            trace_id="trace-001",
            turn_id="turn-001",
            provider_name="lmstudio_responses",
            response_id="resp-001",
            output_text="Hello.",
            finish_reason=FinishReason.STOP,
            usage={},
            raw_metadata={},
            error=None,
        ),
        trace_event,
        error,
        HealthCheck(
            schema_version="0.1-draft",
            service="core",
            status=HealthStatus.OK,
            version="0.1.0",
            uptime_seconds=1.5,
            dependencies={},
        ),
        VersionInfo(
            schema_version="0.1-draft",
            service="core",
            service_version="0.1.0",
            contract_versions={"TurnInput": "0.1-draft"},
            build={},
        ),
    ]

    for example in examples:
        serialized = example.model_dump_json()
        restored = type(example).model_validate_json(serialized)
        assert restored.model_dump(mode="json") == example.model_dump(mode="json")


def test_turn_input_previous_response_id_round_trips_when_null():
    turn = TurnInput(
        schema_version="0.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        input_text="Hello",
        previous_response_id=None,
        source=Source.CLI,
        metadata={},
    )

    restored = TurnInput.model_validate_json(turn.model_dump_json())

    assert restored.previous_response_id is None
