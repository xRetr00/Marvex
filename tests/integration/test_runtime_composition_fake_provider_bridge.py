from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import pytest

from packages.assistant_runtime.input_normalization import (
    build_text_input_event,
    build_turn_input_from_event,
)
from packages.contracts import (
    ErrorCode,
    ErrorEnvelope,
    FinishReason,
    ProviderRequest,
    ProviderResponse,
    TraceEvent,
    TraceStage,
)


def make_turn_input(*, text: str = "Hello from runtime composition") -> object:
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id="trace-runtime-composition",
        event_id="event-runtime-composition",
        text=text,
        timestamp=datetime(2026, 5, 12, 12, 0, tzinfo=UTC),
    )
    return build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id="trace-runtime-composition",
        turn_id="turn-runtime-composition",
        input_event=event,
    )


class RecordingTelemetrySink:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def emit(self, event: TraceEvent) -> None:
        self.events.append(event)


class RecordingProvider:
    def __init__(self, response: ProviderResponse) -> None:
        self.requests: list[ProviderRequest] = []
        self.response = response

    def send(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        return self.response.model_copy(
            update={
                "schema_version": request.schema_version,
                "trace_id": request.trace_id,
                "turn_id": request.turn_id,
            }
        )


def provider_error_response() -> ProviderResponse:
    return ProviderResponse(
        schema_version="0.1.1-draft",
        trace_id="trace-placeholder",
        turn_id="turn-placeholder",
        provider_name="fake",
        response_id="fake-error-response",
        output_text="",
        finish_reason=FinishReason.ERROR,
        usage={},
        raw_metadata={"unsafe_api_key": "must-not-appear"},
        error=ErrorEnvelope(
            schema_version="0.1.1-draft",
            trace_id="trace-placeholder",
            error_id="fake-provider-error",
            code=ErrorCode.PROVIDER_ERROR,
            message="Fake provider safe error.",
            recoverable=False,
            source="fake_provider",
            details={},
        ),
    )


def empty_provider_response() -> ProviderResponse:
    return ProviderResponse(
        schema_version="0.1.1-draft",
        trace_id="trace-placeholder",
        turn_id="turn-placeholder",
        provider_name="fake",
        response_id="fake-empty-response",
        output_text="",
        finish_reason=FinishReason.STOP,
        usage={},
        raw_metadata={"raw_transcript": "must-not-appear"},
        error=None,
    )


def test_bridge_creates_fake_provider_through_provider_runtime(monkeypatch):
    import packages.runtime_composition.assistant_provider_bridge as bridge

    captured = {}
    real_create_provider = bridge.create_provider

    def recording_create_provider(config):
        captured["config"] = config
        return real_create_provider(config)

    monkeypatch.setattr(bridge, "create_provider", recording_create_provider)

    result = bridge.run_fake_provider_assistant_bridge(
        make_turn_input(),
        model="fake-model",
    )

    assert captured["config"].provider_name == "fake"
    assert result.error is None
    assert result.assistant_final_response is not None
    assert result.assistant_final_response.text == "fake provider response"
    assert result.schema_version == "0.1.1-draft"
    assert result.trace_id == "trace-runtime-composition"
    assert result.turn_id == "turn-runtime-composition"
    assert result.provider_turn_refs[0].provider_name == "fake"
    assert result.provider_turn_refs[0].ref_id == "fake-response-001"


def test_bridge_injects_provider_into_core_helper(monkeypatch):
    import packages.runtime_composition.assistant_provider_bridge as bridge

    captured = {}
    sentinel = object()

    def fake_run_assistant_provider_stage_turn(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return sentinel

    monkeypatch.setattr(
        bridge,
        "run_assistant_provider_stage_turn",
        fake_run_assistant_provider_stage_turn,
    )

    result = bridge.run_fake_provider_assistant_bridge(
        make_turn_input(),
        model="fake-model",
        instructions="Follow policy.",
        previous_response_id="previous-runtime-composition",
        provider_options={"temperature": 0},
    )

    assert result is sentinel
    assert captured["args"][0].turn_id == "turn-runtime-composition"
    assert hasattr(captured["kwargs"]["provider"], "send")
    assert captured["kwargs"]["model"] == "fake-model"
    assert captured["kwargs"]["instructions"] == "Follow policy."
    assert captured["kwargs"]["previous_response_id"] == "previous-runtime-composition"
    assert captured["kwargs"]["provider_options"] == {"temperature": 0}


def test_bridge_reaches_assistant_runtime_provider_stage(monkeypatch):
    import packages.core.orchestration.assistant_provider_stage as core_provider_stage

    captured = {}
    real_run_provider_stage_turn = core_provider_stage.run_provider_stage_turn

    def recording_run_provider_stage_turn(*args, **kwargs):
        captured["called"] = True
        return real_run_provider_stage_turn(*args, **kwargs)

    monkeypatch.setattr(
        core_provider_stage,
        "run_provider_stage_turn",
        recording_run_provider_stage_turn,
    )

    from packages.runtime_composition.assistant_provider_bridge import (
        run_fake_provider_assistant_bridge,
    )

    result = run_fake_provider_assistant_bridge(make_turn_input(), model="fake-model")

    assert captured["called"] is True
    assert result.error is None
    assert result.assistant_final_response is not None


def test_bridge_preserves_previous_response_id_and_does_not_mutate(monkeypatch):
    import packages.runtime_composition.assistant_provider_bridge as bridge

    provider = RecordingProvider(
        ProviderResponse(
            schema_version="0.1.1-draft",
            trace_id="trace-placeholder",
            turn_id="turn-placeholder",
            provider_name="fake",
            response_id="fake-recorded-response",
            output_text="recorded response",
            finish_reason=FinishReason.STOP,
            usage={},
            raw_metadata={},
            error=None,
        )
    )
    monkeypatch.setattr(bridge, "create_provider", lambda config: provider)
    turn_input = make_turn_input().model_copy(update={"metadata": {"safe": "kept"}})
    before = deepcopy(turn_input.model_dump())

    result = bridge.run_fake_provider_assistant_bridge(
        turn_input,
        model="fake-model",
        previous_response_id="previous-runtime-composition",
        provider_options={"temperature": 0},
    )

    assert result.error is None
    assert provider.requests[0].previous_response_id == "previous-runtime-composition"
    assert provider.requests[0].provider_options == {"temperature": 0}
    assert result.provider_turn_refs[0].ref_id == "fake-recorded-response"
    assert turn_input.model_dump() == before


def test_bridge_provider_error_maps_to_safe_assistant_error(monkeypatch):
    import packages.runtime_composition.assistant_provider_bridge as bridge

    monkeypatch.setattr(
        bridge,
        "create_provider",
        lambda config: RecordingProvider(provider_error_response()),
    )

    result = bridge.run_fake_provider_assistant_bridge(make_turn_input(), model="fake-model")

    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.code == ErrorCode.PROVIDER_ERROR
    assert result.error.message == "Fake provider safe error."
    assert result.provider_turn_refs[0].ref_id == "fake-error-response"
    assert "must-not-appear" not in str(result.model_dump())


def test_bridge_empty_provider_output_maps_to_safe_error(monkeypatch):
    import packages.runtime_composition.assistant_provider_bridge as bridge

    monkeypatch.setattr(
        bridge,
        "create_provider",
        lambda config: RecordingProvider(empty_provider_response()),
    )

    result = bridge.run_fake_provider_assistant_bridge(make_turn_input(), model="fake-model")

    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.code == ErrorCode.VALIDATION_ERROR
    assert result.error.message == "Provider output was empty."
    assert result.provider_turn_refs[0].ref_id == "fake-empty-response"
    assert "must-not-appear" not in str(result.model_dump())


def test_bridge_telemetry_uses_assistant_runtime_safe_path():
    from packages.runtime_composition.assistant_provider_bridge import (
        run_fake_provider_assistant_bridge,
    )

    sink = RecordingTelemetrySink()

    result = run_fake_provider_assistant_bridge(
        make_turn_input(),
        model="fake-model",
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
    assert all(event.trace_id == "trace-runtime-composition" for event in sink.events)
    assert "fake provider response" not in str([event.model_dump() for event in sink.events])


def test_cli_imports_only_the_approved_runtime_composition_bridge():
    source = Path("apps/cli/main.py").read_text(encoding="utf-8")

    assert "from packages.runtime_composition import (" in source
    assert "run_fake_provider_assistant_bridge" in source
    assert "run_provider_foundation_turn" in source
    assert "packages.runtime_composition.assistant_provider_bridge" not in source
    assert source.count("run_fake_provider_assistant_bridge") == 2
