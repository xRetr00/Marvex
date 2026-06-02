from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest

from packages.assistant_runtime.input_normalization import (
    build_text_input_event,
    build_turn_input_from_event,
)
from packages.contracts import (
    AssistantTurnResult,
    ErrorCode,
    ErrorEnvelope,
    FinishReason,
    ProviderRequest,
    ProviderResponse,
    StageStatus,
    TraceEvent,
    TraceStage,
)


def make_turn_input(*, text: str | None = "Hello") -> object:
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id="trace-provider-stage",
        event_id="event-provider-stage",
        text=text or "",
        timestamp=datetime(2026, 5, 12, 12, 0, tzinfo=UTC),
    )
    turn_input = build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id="trace-provider-stage",
        turn_id="turn-provider-stage",
        input_event=event,
    )
    if text is None:
        return turn_input.model_copy(update={"user_visible_input": None})
    return turn_input


class RecordingProvider:
    def __init__(self, response: ProviderResponse | None = None) -> None:
        self.requests: list[ProviderRequest] = []
        self.response = response

    def send(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        if self.response is not None:
            return self.response
        return ProviderResponse(
            schema_version=request.schema_version,
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            provider_name="recording_provider",
            response_id="provider-response-001",
            output_text="Provider response text.",
            finish_reason=FinishReason.STOP,
            usage={"input_count": 2, "output_count": 3},
            raw_metadata={},
            error=None,
        )


class RaisingProvider:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc
        self.requests: list[ProviderRequest] = []

    def send(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        raise self.exc


class RecordingTelemetrySink:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def emit(self, event: TraceEvent) -> None:
        self.events.append(event)


def provider_response_error(code: ErrorCode = ErrorCode.PROVIDER_ERROR) -> ProviderResponse:
    return ProviderResponse(
        schema_version="0.1.1-draft",
        trace_id="trace-provider-stage",
        turn_id="turn-provider-stage",
        provider_name="recording_provider",
        response_id="provider-response-error",
        output_text="",
        finish_reason=FinishReason.ERROR,
        usage={},
        raw_metadata={},
        error=ErrorEnvelope(
            schema_version="0.1.1-draft",
            trace_id="trace-provider-stage",
            error_id="provider-error-001",
            code=code,
            message="Provider returned a safe error.",
            recoverable=False,
            source="provider",
            details={},
        ),
    )


def run_provider_stage(*args, **kwargs) -> AssistantTurnResult:
    from packages.assistant_runtime.provider_stage import run_provider_stage_turn

    return run_provider_stage_turn(*args, **kwargs)


def test_successful_injected_provider_response_becomes_assistant_turn_result():
    provider = RecordingProvider()

    result = run_provider_stage(
        make_turn_input(),
        provider=provider,
        model="neutral-model",
        instructions="Follow assistant policy.",
    )

    assert isinstance(result, AssistantTurnResult)
    assert result.error is None
    assert result.assistant_final_response is not None
    assert result.assistant_final_response.text == "Provider response text."
    assert result.assistant_final_response.finish_reason.value == "stop"
    assert result.schema_version == "0.1.1-draft"
    assert result.trace_id == "trace-provider-stage"
    assert result.turn_id == "turn-provider-stage"
    assert [stage.stage_name for stage in result.stage_summaries] == [
        "input_normalization",
        "provider_stage",
        "final_response_assembly",
    ]
    assert [stage.status for stage in result.stage_summaries] == [
        StageStatus.COMPLETED,
        StageStatus.COMPLETED,
        StageStatus.COMPLETED,
    ]
    assert len(result.provider_turn_refs) == 1
    assert result.provider_turn_refs[0].ref_id == "provider-response-001"
    assert result.provider_turn_refs[0].stage_name == "provider_stage"


def test_provider_request_preserves_ids_and_explicit_previous_response_id():
    provider = RecordingProvider()
    turn_input = make_turn_input()

    result = run_provider_stage(
        turn_input,
        provider=provider,
        model="neutral-model",
        previous_response_id="previous-response-001",
        provider_options={"temperature": 0},
    )

    assert result.trace_id == turn_input.trace_id
    assert result.turn_id == turn_input.turn_id
    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.schema_version == turn_input.schema_version
    assert request.trace_id == turn_input.trace_id
    assert request.turn_id == turn_input.turn_id
    assert request.input_text == "Hello"
    assert request.previous_response_id == "previous-response-001"
    assert request.model == "neutral-model"
    assert request.provider_options == {"temperature": 0}


def test_turn_input_metadata_is_not_used_as_hidden_previous_response_state():
    provider = RecordingProvider()
    turn_input = make_turn_input().model_copy(
        update={"metadata": {"previous_response_id": "hidden-response"}}
    )

    run_provider_stage(turn_input, provider=provider, model="neutral-model")

    assert provider.requests[0].previous_response_id is None


def test_provider_error_response_maps_to_safe_assistant_error_result():
    result = run_provider_stage(
        make_turn_input(),
        provider=RecordingProvider(provider_response_error(ErrorCode.PROVIDER_ERROR)),
        model="neutral-model",
    )

    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.code == ErrorCode.PROVIDER_ERROR
    assert result.error.message == "Provider returned a safe error."
    assert result.provider_turn_refs[0].ref_id == "provider-response-error"
    assert [(stage.stage_name, stage.status) for stage in result.stage_summaries] == [
        ("input_normalization", StageStatus.COMPLETED),
        ("provider_stage", StageStatus.FAILED),
    ]


@pytest.mark.parametrize(
    ("exc", "code", "message"),
    [
        (TimeoutError("raw timeout detail"), ErrorCode.PROVIDER_TIMEOUT, "Provider request timed out."),
        (ConnectionError("raw unavailable detail"), ErrorCode.PROVIDER_UNAVAILABLE, "Provider unavailable."),
        (RuntimeError("raw provider detail"), ErrorCode.PROVIDER_ERROR, "Provider stage failed."),
    ],
)
def test_provider_failures_map_to_deterministic_safe_errors(exc, code, message):
    result = run_provider_stage(
        make_turn_input(),
        provider=RaisingProvider(exc),
        model="neutral-model",
    )

    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.code == code
    assert result.error.message == message
    assert str(exc) not in str(result.model_dump())


@pytest.mark.parametrize("output_text", ["", "   "])
def test_empty_provider_output_maps_to_validation_error(output_text: str):
    provider = RecordingProvider(
        ProviderResponse(
            schema_version="0.1.1-draft",
            trace_id="trace-provider-stage",
            turn_id="turn-provider-stage",
            provider_name="recording_provider",
            response_id="provider-empty-output",
            output_text=output_text,
            finish_reason=FinishReason.STOP,
            usage={},
            raw_metadata={},
            error=None,
        )
    )

    result = run_provider_stage(make_turn_input(), provider=provider, model="neutral-model")

    assert result.error is not None
    assert result.error.code == ErrorCode.VALIDATION_ERROR
    assert result.error.message == "Provider output was empty."
    assert result.assistant_final_response is None


def test_provider_stage_emits_trace_lifecycle_through_telemetry_sink():
    sink = RecordingTelemetrySink()

    result = run_provider_stage(
        make_turn_input(),
        provider=RecordingProvider(),
        model="neutral-model",
        telemetry_sink=sink,
    )

    assert result.error is None
    assert [event.stage for event in sink.events] == [
        TraceStage.PROVIDER_REQUEST_CREATED,
        TraceStage.PROVIDER_REQUEST_SENT,
        TraceStage.PROVIDER_RESPONSE_RECEIVED,
        TraceStage.FINAL_RESPONSE_CREATED,
        TraceStage.TURN_COMPLETED,
    ]
    assert all(event.trace_id == "trace-provider-stage" for event in sink.events)
    assert sink.events[0].data == {
        "stage": "provider_stage",
        "model": "neutral-model",
        "previous_response_id_present": False,
    }
    assert sink.events[2].data["status"] == "success"


def test_provider_stage_failure_trace_uses_safe_telemetry_data():
    sink = RecordingTelemetrySink()

    result = run_provider_stage(
        make_turn_input(),
        provider=RaisingProvider(RuntimeError("raw provider secret")),
        model="neutral-model",
        telemetry_sink=sink,
    )

    assert result.error is not None
    assert [event.stage for event in sink.events] == [
        TraceStage.PROVIDER_REQUEST_CREATED,
        TraceStage.PROVIDER_REQUEST_SENT,
        TraceStage.PROVIDER_RESPONSE_RECEIVED,
    ]
    dumped = str([event.model_dump() for event in sink.events])
    assert "raw provider secret" not in dumped
    assert sink.events[-1].data == {
        "stage": "provider_stage",
        "status": "provider_error",
        "error_code": ErrorCode.PROVIDER_ERROR.value,
        "provider_response_id_present": False,
    }


def test_input_objects_are_not_mutated():
    turn_input = make_turn_input().model_copy(
        update={"metadata": {"safe_case": "kept"}}
    )
    before = deepcopy(turn_input.model_dump())

    run_provider_stage(turn_input, provider=RecordingProvider(), model="neutral-model")

    assert turn_input.model_dump() == before


def test_provider_stage_is_not_wired_into_normal_assistant_runtime():
    source = Path("packages/assistant_runtime/runtime.py").read_text(encoding="utf-8")

    assert "provider_stage" not in source
    assert "run_provider_stage_turn" not in source


def test_provider_stage_is_not_wired_into_core_or_cli_product_paths():
    scanned_paths = [
        Path("packages/core/orchestration/turn_orchestrator.py"),
        *Path("apps/cli").rglob("*.py"),
    ]

    for path in scanned_paths:
        source = path.read_text(encoding="utf-8")
        assert "run_provider_stage_turn" not in source
        assert "packages.assistant_runtime.provider_stage" not in source


def test_provider_stage_source_has_no_concrete_provider_or_runtime_imports():
    source = Path("packages/assistant_runtime/provider_stage.py").read_text(
        encoding="utf-8"
    )
    forbidden = [
        "packages.provider_runtime",
        "packages.adapters",
        "packages.ports",
        "LMStudio",
        "litellm",
        "LiteLLM",
        "OpenAI",
        "Anthropic",
        "Gemini",
        "model routing",
        "retry",
        "session history",
    ]

    assert [term for term in forbidden if term in source] == []


def test_provider_stage_uses_telemetry_event_construction_not_sanitizer_policy():
    source = Path("packages/assistant_runtime/provider_stage.py").read_text(
        encoding="utf-8"
    )

    assert "make_trace_event" in source
    assert "sanitize_trace_data" not in source
    assert "assert_trace_data_safe" not in source
