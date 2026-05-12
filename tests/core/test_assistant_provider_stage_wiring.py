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


def make_turn_input(*, text: str | None = "Hello from Core") -> object:
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id="trace-core-provider-stage",
        event_id="event-core-provider-stage",
        text=text or "",
        timestamp=datetime(2026, 5, 12, 12, 0, tzinfo=UTC),
    )
    turn_input = build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id="trace-core-provider-stage",
        turn_id="turn-core-provider-stage",
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
            provider_name="neutral_provider",
            response_id="provider-response-core-001",
            output_text="Provider-stage response from Core seam.",
            finish_reason=FinishReason.STOP,
            usage={"input_count": 3, "output_count": 5},
            raw_metadata={},
            error=None,
        )


class RaisingProvider:
    def __init__(self, exc: Exception) -> None:
        self.requests: list[ProviderRequest] = []
        self.exc = exc

    def send(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        raise self.exc


class RecordingTelemetrySink:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def emit(self, event: TraceEvent) -> None:
        self.events.append(event)


def provider_error_response(code: ErrorCode = ErrorCode.PROVIDER_ERROR) -> ProviderResponse:
    return ProviderResponse(
        schema_version="0.1.1-draft",
        trace_id="trace-core-provider-stage",
        turn_id="turn-core-provider-stage",
        provider_name="neutral_provider",
        response_id="provider-response-core-error",
        output_text="",
        finish_reason=FinishReason.ERROR,
        usage={},
        raw_metadata={},
        error=ErrorEnvelope(
            schema_version="0.1.1-draft",
            trace_id="trace-core-provider-stage",
            error_id="provider-core-error-001",
            code=code,
            message="Provider returned a safe error.",
            recoverable=False,
            source="provider",
            details={},
        ),
    )


def run_core_provider_stage(*args, **kwargs) -> AssistantTurnResult:
    from packages.core.orchestration.assistant_provider_stage import (
        run_assistant_provider_stage_turn,
    )

    return run_assistant_provider_stage_turn(*args, **kwargs)


def test_core_helper_delegates_to_assistant_runtime_provider_stage(monkeypatch):
    import packages.core.orchestration.assistant_provider_stage as core_provider_stage

    turn_input = make_turn_input()
    provider = RecordingProvider()
    sink = RecordingTelemetrySink()
    sentinel = object()
    captured = {}

    def fake_run_provider_stage_turn(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return sentinel

    monkeypatch.setattr(
        core_provider_stage,
        "run_provider_stage_turn",
        fake_run_provider_stage_turn,
    )

    result = core_provider_stage.run_assistant_provider_stage_turn(
        turn_input,
        provider=provider,
        model="neutral-model",
        instructions="Follow assistant policy.",
        previous_response_id="previous-response-core",
        provider_options={"temperature": 0},
        telemetry_sink=sink,
    )

    assert result is sentinel
    assert captured["args"] == (turn_input,)
    assert captured["kwargs"] == {
        "provider": provider,
        "model": "neutral-model",
        "instructions": "Follow assistant policy.",
        "previous_response_id": "previous-response-core",
        "provider_options": {"temperature": 0},
        "telemetry_sink": sink,
    }


def test_successful_injected_provider_response_becomes_assistant_turn_result():
    result = run_core_provider_stage(
        make_turn_input(),
        provider=RecordingProvider(),
        model="neutral-model",
        instructions="Follow assistant policy.",
    )

    assert isinstance(result, AssistantTurnResult)
    assert result.error is None
    assert result.assistant_final_response is not None
    assert result.assistant_final_response.text == "Provider-stage response from Core seam."
    assert result.schema_version == "0.1.1-draft"
    assert result.trace_id == "trace-core-provider-stage"
    assert result.turn_id == "turn-core-provider-stage"
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
    assert result.provider_turn_refs[0].ref_id == "provider-response-core-001"
    assert result.provider_turn_refs[0].stage_name == "provider_stage"


def test_previous_response_id_is_passed_through_explicitly():
    provider = RecordingProvider()

    result = run_core_provider_stage(
        make_turn_input(),
        provider=provider,
        model="neutral-model",
        previous_response_id="previous-response-core",
        provider_options={"temperature": 0},
    )

    assert result.error is None
    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.schema_version == "0.1.1-draft"
    assert request.trace_id == "trace-core-provider-stage"
    assert request.turn_id == "turn-core-provider-stage"
    assert request.input_text == "Hello from Core"
    assert request.previous_response_id == "previous-response-core"
    assert request.provider_options == {"temperature": 0}


def test_provider_error_response_maps_to_deterministic_safe_error():
    result = run_core_provider_stage(
        make_turn_input(),
        provider=RecordingProvider(provider_error_response(ErrorCode.PROVIDER_ERROR)),
        model="neutral-model",
    )

    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.code == ErrorCode.PROVIDER_ERROR
    assert result.error.message == "Provider returned a safe error."
    assert result.provider_turn_refs[0].ref_id == "provider-response-core-error"
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
def test_provider_exceptions_map_to_deterministic_safe_errors(exc, code, message):
    result = run_core_provider_stage(
        make_turn_input(),
        provider=RaisingProvider(exc),
        model="neutral-model",
    )

    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.code == code
    assert result.error.message == message
    assert str(exc) not in str(result.model_dump())


def test_empty_provider_output_maps_to_validation_error():
    provider = RecordingProvider(
        ProviderResponse(
            schema_version="0.1.1-draft",
            trace_id="trace-core-provider-stage",
            turn_id="turn-core-provider-stage",
            provider_name="neutral_provider",
            response_id="provider-empty-output",
            output_text="",
            finish_reason=FinishReason.STOP,
            usage={},
            raw_metadata={},
            error=None,
        )
    )

    result = run_core_provider_stage(make_turn_input(), provider=provider, model="neutral-model")

    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.code == ErrorCode.VALIDATION_ERROR
    assert result.error.message == "Provider output was empty."


def test_trace_lifecycle_is_emitted_through_assistant_runtime_safe_path():
    sink = RecordingTelemetrySink()

    result = run_core_provider_stage(
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
    assert all(event.trace_id == "trace-core-provider-stage" for event in sink.events)
    assert sink.events[0].data == {"stage": "provider_stage"}
    assert sink.events[2].data["status"] == "success"


def test_input_objects_are_not_mutated():
    turn_input = make_turn_input().model_copy(update={"metadata": {"safe": "kept"}})
    before = deepcopy(turn_input.model_dump())

    run_core_provider_stage(turn_input, provider=RecordingProvider(), model="neutral-model")

    assert turn_input.model_dump() == before


def test_core_provider_stage_helper_is_not_wired_into_existing_product_paths():
    orchestrator_source = Path(
        "packages/core/orchestration/turn_orchestrator.py"
    ).read_text(encoding="utf-8")
    cli_source = Path("apps/cli/main.py").read_text(encoding="utf-8")
    default_turn_path = cli_source.split("def _run_turn", 1)[1].split(
        "def _run_assistant_runtime_provider_stage_fake", 1
    )[0]

    assert "run_assistant_provider_stage_turn" not in orchestrator_source
    assert "packages.core.orchestration.assistant_provider_stage" not in orchestrator_source
    assert "packages.assistant_runtime.provider_stage" not in orchestrator_source
    assert "run_assistant_provider_stage_turn" not in default_turn_path


def test_core_helper_source_has_no_provider_runtime_or_concrete_provider_imports():
    source = Path("packages/core/orchestration/assistant_provider_stage.py").read_text(
        encoding="utf-8"
    )
    forbidden = [
        "packages.provider_runtime",
        "packages.adapters",
        "lmstudio",
        "litellm",
        "openai",
        "openrouter",
        "anthropic",
        "gemini",
        "model routing",
        "retry",
        "session history",
        "global",
    ]

    assert [term for term in forbidden if term in source.lower()] == []
    assert "run_provider_stage_turn" in source


def test_assistant_runtime_provider_stage_still_has_no_runtime_or_adapter_imports():
    source = Path("packages/assistant_runtime/provider_stage.py").read_text(
        encoding="utf-8"
    )
    forbidden = [
        "packages.provider_runtime",
        "packages.adapters",
        "packages.ports",
    ]

    assert [term for term in forbidden if term in source] == []
