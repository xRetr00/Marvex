from pathlib import Path

from packages.adapters.providers.fake import (
    FakeProvider,
    FakeProviderConfig,
    FakeProviderMode,
)
from packages.contracts import (
    ErrorCode,
    ErrorEnvelope,
    FinalResponse,
    FinishReason,
    ProviderRequest,
    ProviderResponse,
    ResponseType,
    Source,
    TraceEvent,
    TraceStage,
    TurnInput,
    TurnOutput,
)
from packages.core.orchestration import TurnOrchestrator
from packages.ports.provider import ProviderPort
from packages.telemetry import NoopTelemetrySink


def make_turn_input(previous_response_id: str | None = "prev-001") -> TurnInput:
    return TurnInput(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        input_text="Hello",
        previous_response_id=previous_response_id,
        source=Source.CLI,
        metadata={},
    )


class RecordingTelemetrySink:
    def __init__(self) -> None:
        self.events: list[TraceEvent] = []

    def emit(self, event: TraceEvent) -> None:
        self.events.append(event)


def event_stages(sink: RecordingTelemetrySink) -> list[TraceStage]:
    return [event.stage for event in sink.events]


def test_successful_turn_with_injected_fake_provider():
    provider = FakeProvider(
        FakeProviderConfig(output_text="fake output", response_id="resp-001")
    )
    output = TurnOrchestrator(provider).run_turn(make_turn_input())

    validated = TurnOutput.model_validate(output.model_dump())
    assert validated.schema_version == "0.1.1-draft"
    assert validated.trace_id == "trace-001"
    assert validated.turn_id == "turn-001"
    assert validated.final_response.text == "fake output"
    assert validated.final_response.response_type == ResponseType.TEXT
    assert validated.final_response.finish_reason == FinishReason.STOP
    assert validated.final_response.safe_for_tts is True
    assert validated.provider_response_id == "resp-001"
    assert validated.events == []
    assert validated.error is None


def test_successful_turn_emits_lifecycle_in_order():
    sink = RecordingTelemetrySink()
    provider = FakeProvider(
        FakeProviderConfig(output_text="fake output", response_id="resp-001")
    )

    output = TurnOrchestrator(provider, telemetry_sink=sink).run_turn(
        make_turn_input()
    )

    assert output.events == []
    assert event_stages(sink) == [
        TraceStage.TURN_RECEIVED,
        TraceStage.PROVIDER_REQUEST_CREATED,
        TraceStage.PROVIDER_REQUEST_SENT,
        TraceStage.PROVIDER_RESPONSE_RECEIVED,
        TraceStage.FINAL_RESPONSE_CREATED,
        TraceStage.TURN_COMPLETED,
    ]
    for event in sink.events:
        assert TraceEvent.model_validate(event.model_dump()).trace_id == "trace-001"


def test_provider_error_turn_with_injected_fake_provider():
    provider = FakeProvider(
        FakeProviderConfig(
            mode=FakeProviderMode.ERROR,
            response_id="resp-error",
            error_code=ErrorCode.PROVIDER_TIMEOUT,
            error_message="Provider failed.",
        )
    )
    output = TurnOrchestrator(provider).run_turn(make_turn_input())

    validated = TurnOutput.model_validate(output.model_dump())
    assert validated.provider_response_id == "resp-error"
    assert validated.error is not None
    assert validated.error.code == ErrorCode.PROVIDER_TIMEOUT
    assert validated.final_response.text == "Provider failed."
    assert validated.final_response.response_type == ResponseType.ERROR
    assert validated.final_response.finish_reason == FinishReason.ERROR
    assert validated.final_response.safe_for_tts is False


def test_provider_error_response_emits_completed_lifecycle_with_error_data():
    sink = RecordingTelemetrySink()
    provider = FakeProvider(
        FakeProviderConfig(
            mode=FakeProviderMode.ERROR,
            response_id="resp-error",
            error_code=ErrorCode.PROVIDER_TIMEOUT,
            error_message="Provider failed.",
        )
    )

    output = TurnOrchestrator(provider, telemetry_sink=sink).run_turn(
        make_turn_input()
    )

    assert output.error is not None
    assert event_stages(sink) == [
        TraceStage.TURN_RECEIVED,
        TraceStage.PROVIDER_REQUEST_CREATED,
        TraceStage.PROVIDER_REQUEST_SENT,
        TraceStage.PROVIDER_RESPONSE_RECEIVED,
        TraceStage.FINAL_RESPONSE_CREATED,
        TraceStage.TURN_COMPLETED,
    ]
    completed = sink.events[-1]
    assert completed.data["status"] == "provider_error"
    assert completed.data["error_code"] == ErrorCode.PROVIDER_TIMEOUT.value
    assert completed.data["error_message"] == "Provider failed."


class RaisingProvider:
    def send(self, request: ProviderRequest) -> ProviderResponse:
        raise RuntimeError("provider exploded")


def test_unexpected_provider_exception_emits_turn_failed_and_reraises():
    sink = RecordingTelemetrySink()
    orchestrator = TurnOrchestrator(RaisingProvider(), telemetry_sink=sink)

    try:
        orchestrator.run_turn(make_turn_input())
    except RuntimeError as exc:
        assert str(exc) == "provider exploded"
    else:
        raise AssertionError("provider exception should be re-raised")

    assert event_stages(sink) == [
        TraceStage.TURN_RECEIVED,
        TraceStage.PROVIDER_REQUEST_CREATED,
        TraceStage.PROVIDER_REQUEST_SENT,
        TraceStage.TURN_FAILED,
    ]
    failed = sink.events[-1]
    assert failed.data["status"] == "exception"
    assert failed.data["error_type"] == "RuntimeError"


class RecordingProvider:
    def __init__(self) -> None:
        self.requests: list[ProviderRequest] = []

    def send(self, request: ProviderRequest) -> ProviderResponse:
        self.requests.append(request)
        return ProviderResponse(
            schema_version=request.schema_version,
            trace_id=request.trace_id,
            turn_id=request.turn_id,
            provider_name="recording",
            response_id="recorded-response",
            output_text="recorded output",
            finish_reason=FinishReason.STOP,
            usage={},
            raw_metadata={},
            error=None,
        )


def test_previous_response_id_is_copied_directly_to_provider_request():
    provider = RecordingProvider()
    orchestrator = TurnOrchestrator(
        provider,
        model="configured-model",
        instructions="configured instructions",
        provider_options={"temperature": 0},
    )

    orchestrator.run_turn(make_turn_input(previous_response_id="prev-direct"))

    assert len(provider.requests) == 1
    request = provider.requests[0]
    assert request.schema_version == "0.1.1-draft"
    assert request.trace_id == "trace-001"
    assert request.turn_id == "turn-001"
    assert request.input_text == "Hello"
    assert request.previous_response_id == "prev-direct"
    assert request.model == "configured-model"
    assert request.instructions == "configured instructions"
    assert request.provider_options == {"temperature": 0}


def test_provider_response_id_is_copied_to_turn_output():
    output = TurnOrchestrator(RecordingProvider()).run_turn(make_turn_input())

    assert output.provider_response_id == "recorded-response"


def test_turn_orchestrator_accepts_provider_port_compatible_provider():
    provider = RecordingProvider()

    assert isinstance(provider, ProviderPort)
    assert TurnOrchestrator(provider).run_turn(make_turn_input()).provider_response_id


class BadProviderWithoutSend:
    pass


class BadProviderReturningObject:
    def send(self, request: ProviderRequest) -> object:
        return object()


def test_bad_provider_without_send_is_not_provider_port():
    assert not isinstance(BadProviderWithoutSend(), ProviderPort)


def test_bad_provider_returning_non_contract_object_fails_orchestrator_path():
    orchestrator = TurnOrchestrator(BadProviderReturningObject())

    try:
        orchestrator.run_turn(make_turn_input())
    except AttributeError as exc:
        assert "provider_name" in str(exc)
    else:
        raise AssertionError("bad provider response should fail orchestrator path")


def test_output_is_deterministic_for_same_input_and_provider_config():
    provider = FakeProvider(
        FakeProviderConfig(output_text="deterministic", response_id="resp-fixed")
    )
    orchestrator = TurnOrchestrator(provider)
    turn_input = make_turn_input(previous_response_id=None)

    first = orchestrator.run_turn(turn_input)
    second = orchestrator.run_turn(turn_input)

    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_noop_sink_preserves_existing_output_behavior():
    provider = FakeProvider(
        FakeProviderConfig(output_text="fake output", response_id="resp-001")
    )
    turn_input = make_turn_input()

    without_sink = TurnOrchestrator(provider).run_turn(turn_input)
    with_noop = TurnOrchestrator(
        provider, telemetry_sink=NoopTelemetrySink()
    ).run_turn(turn_input)

    assert without_sink.model_dump(mode="json") == with_noop.model_dump(mode="json")


def test_orchestrator_source_has_no_forbidden_imports_or_tokens():
    source = (
        Path("packages")
        / "core"
        / "orchestration"
        / "turn_orchestrator.py"
    ).read_text(encoding="utf-8")
    lowered = source.lower()
    forbidden = [
        "packages.adapters",
        "fakeprovider",
        "lmstudio",
        "httpx",
        "requests",
        "urllib",
        "socket",
        "subprocess",
        "open(",
        "cli",
        "tool",
        "memory",
        "intent",
        "voice",
        "desktop",
        "logging",
        "open(",
    ]

    assert [token for token in forbidden if token in lowered] == []
    assert "from packages.ports.provider import ProviderPort" in source


def test_orchestrator_source_does_not_use_metadata_for_previous_response_id():
    source = (
        Path("packages")
        / "core"
        / "orchestration"
        / "turn_orchestrator.py"
    ).read_text(encoding="utf-8")

    assert "metadata.previous_response_id" not in source
    assert "metadata.get" not in source
    assert "previous_response_id=turn_input.previous_response_id" in source
