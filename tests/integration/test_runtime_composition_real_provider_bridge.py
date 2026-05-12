from copy import deepcopy
from datetime import UTC, datetime

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


def make_turn_input(*, text: str = "Hello from real provider proof") -> object:
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id="trace-real-provider-proof",
        event_id="event-real-provider-proof",
        text=text,
        timestamp=datetime(2026, 5, 12, 12, 0, tzinfo=UTC),
    )
    return build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id="trace-real-provider-proof",
        turn_id="turn-real-provider-proof",
        input_event=event,
    )


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


class RecordingTelemetrySink:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def emit(self, event: TraceEvent) -> None:
        self.events.append(event)


def success_response() -> ProviderResponse:
    return ProviderResponse(
        schema_version="0.1.1-draft",
        trace_id="trace-placeholder",
        turn_id="turn-placeholder",
        provider_name="lmstudio_responses",
        response_id="lmstudio-response-001",
        output_text="LM Studio proof response.",
        finish_reason=FinishReason.STOP,
        usage={"input_tokens": 3, "output_tokens": 4},
        raw_metadata={"raw_provider_preview": "must-not-leak"},
        error=None,
    )


def provider_error_response() -> ProviderResponse:
    return ProviderResponse(
        schema_version="0.1.1-draft",
        trace_id="trace-placeholder",
        turn_id="turn-placeholder",
        provider_name="lmstudio_responses",
        response_id="lmstudio-error-response",
        output_text="",
        finish_reason=FinishReason.ERROR,
        usage={},
        raw_metadata={"raw_api_key": "must-not-leak"},
        error=ErrorEnvelope(
            schema_version="0.1.1-draft",
            trace_id="trace-placeholder",
            error_id="lmstudio-safe-error",
            code=ErrorCode.PROVIDER_ERROR,
            message="Provider returned a safe error.",
            recoverable=True,
            source="lmstudio_responses_provider",
            details={},
        ),
    )


def empty_response() -> ProviderResponse:
    return ProviderResponse(
        schema_version="0.1.1-draft",
        trace_id="trace-placeholder",
        turn_id="turn-placeholder",
        provider_name="lmstudio_responses",
        response_id="lmstudio-empty-response",
        output_text="",
        finish_reason=FinishReason.STOP,
        usage={},
        raw_metadata={"raw_transcript": "must-not-leak"},
        error=None,
    )


def test_real_provider_bridge_creates_provider_through_provider_runtime(monkeypatch):
    import packages.runtime_composition.assistant_provider_bridge as bridge

    captured = {}
    provider = RecordingProvider(success_response())

    def recording_create_provider(config):
        captured["config"] = config
        return provider

    monkeypatch.setattr(bridge, "create_provider", recording_create_provider)

    result = bridge.run_lmstudio_responses_assistant_bridge(
        make_turn_input(),
        model="local-model",
    )

    assert captured["config"].provider_name == "lmstudio_responses"
    assert result.error is None
    assert result.assistant_final_response is not None
    assert result.assistant_final_response.text == "LM Studio proof response."
    assert result.schema_version == "0.1.1-draft"
    assert result.trace_id == "trace-real-provider-proof"
    assert result.turn_id == "turn-real-provider-proof"
    assert result.provider_turn_refs[0].provider_name == "lmstudio_responses"
    assert result.provider_turn_refs[0].ref_id == "lmstudio-response-001"


def test_real_provider_bridge_injects_provider_into_core_helper(monkeypatch):
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

    result = bridge.run_lmstudio_responses_assistant_bridge(
        make_turn_input(),
        model="local-model",
        instructions="Follow policy.",
        previous_response_id="previous-real-provider",
        provider_options={"temperature": 0},
    )

    assert result is sentinel
    assert captured["args"][0].turn_id == "turn-real-provider-proof"
    assert hasattr(captured["kwargs"]["provider"], "send")
    assert captured["kwargs"]["model"] == "local-model"
    assert captured["kwargs"]["instructions"] == "Follow policy."
    assert captured["kwargs"]["previous_response_id"] == "previous-real-provider"
    assert captured["kwargs"]["provider_options"] == {"temperature": 0}


def test_real_provider_bridge_reaches_assistant_runtime_provider_stage(monkeypatch):
    import packages.core.orchestration.assistant_provider_stage as core_provider_stage
    import packages.runtime_composition.assistant_provider_bridge as bridge

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
    monkeypatch.setattr(
        bridge,
        "create_provider",
        lambda config: RecordingProvider(success_response()),
    )

    result = bridge.run_lmstudio_responses_assistant_bridge(
        make_turn_input(),
        model="local-model",
    )

    assert captured["called"] is True
    assert result.error is None


def test_real_provider_bridge_preserves_previous_response_id_and_does_not_mutate(
    monkeypatch,
):
    import packages.runtime_composition.assistant_provider_bridge as bridge

    provider = RecordingProvider(success_response())
    monkeypatch.setattr(bridge, "create_provider", lambda config: provider)
    turn_input = make_turn_input().model_copy(update={"metadata": {"safe": "kept"}})
    before = deepcopy(turn_input.model_dump())

    result = bridge.run_lmstudio_responses_assistant_bridge(
        turn_input,
        model="local-model",
        previous_response_id="previous-real-provider",
        provider_options={"temperature": 0},
    )

    assert result.error is None
    assert provider.requests[0].previous_response_id == "previous-real-provider"
    assert provider.requests[0].provider_options == {"temperature": 0}
    assert turn_input.model_dump() == before


def test_real_provider_bridge_provider_error_maps_to_safe_assistant_error(
    monkeypatch,
):
    import packages.runtime_composition.assistant_provider_bridge as bridge

    monkeypatch.setattr(
        bridge,
        "create_provider",
        lambda config: RecordingProvider(provider_error_response()),
    )

    result = bridge.run_lmstudio_responses_assistant_bridge(
        make_turn_input(),
        model="local-model",
    )

    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.code == ErrorCode.PROVIDER_ERROR
    assert result.error.message == "Provider returned a safe error."
    assert result.provider_turn_refs[0].ref_id == "lmstudio-error-response"
    assert "must-not-leak" not in str(result.model_dump())


def test_real_provider_bridge_empty_output_maps_to_safe_error(monkeypatch):
    import packages.runtime_composition.assistant_provider_bridge as bridge

    monkeypatch.setattr(
        bridge,
        "create_provider",
        lambda config: RecordingProvider(empty_response()),
    )

    result = bridge.run_lmstudio_responses_assistant_bridge(
        make_turn_input(),
        model="local-model",
    )

    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.code == ErrorCode.VALIDATION_ERROR
    assert result.error.message == "Provider output was empty."
    assert result.provider_turn_refs[0].ref_id == "lmstudio-empty-response"
    assert "must-not-leak" not in str(result.model_dump())


def test_real_provider_bridge_telemetry_uses_existing_safe_path(monkeypatch):
    import packages.runtime_composition.assistant_provider_bridge as bridge

    sink = RecordingTelemetrySink()
    monkeypatch.setattr(
        bridge,
        "create_provider",
        lambda config: RecordingProvider(success_response()),
    )

    result = bridge.run_lmstudio_responses_assistant_bridge(
        make_turn_input(),
        model="local-model",
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
    assert all(event.trace_id == "trace-real-provider-proof" for event in sink.events)
    dumped = str([event.model_dump() for event in sink.events])
    assert "LM Studio proof response." not in dumped
    assert "must-not-leak" not in dumped
