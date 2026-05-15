from __future__ import annotations

import json
from datetime import UTC, datetime
from io import BytesIO
from wsgiref.util import setup_testing_defaults

from packages.assistant_runtime.input_normalization import (
    build_text_input_event,
    build_turn_input_from_event,
)
from packages.contracts import (
    AssistantTurnResult,
    ErrorCode,
    FinishReason,
    ProviderRequest,
    ProviderResponse,
    TraceLevel,
    TraceStage,
)
from packages.local_api.health_version_api import (
    LOCAL_TURNS_LMSTUDIO_RESPONSES_EXECUTION_MODE,
    LocalTurnRequestEnvelope,
    create_health_version_api_app,
)
from packages.telemetry import make_trace_event


EXPECTED_TOKEN = "fake-local-token"
LMSTUDIO_MODE = "assistant_runtime_lmstudio_responses"


class RecordingServer:
    def __init__(self) -> None:
        self.served = False
        self.closed = False

    def serve_forever(self) -> None:
        self.served = True

    def server_close(self) -> None:
        self.closed = True


class RaisingProvider:
    def __init__(self, exc: Exception) -> None:
        self.exc = exc

    def send(self, _request: ProviderRequest) -> ProviderResponse:
        raise self.exc


class MalformedProvider:
    def send(self, _request: ProviderRequest) -> object:
        return object()


def make_turn_input(*, trace_id: str = "trace-local-api-lmstudio"):
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id=trace_id,
        event_id="event-local-api-lmstudio",
        text="Hello through local API LM Studio",
        timestamp=datetime(2026, 5, 15, 12, 0, tzinfo=UTC),
    )
    return build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id=trace_id,
        turn_id="turn-local-api-lmstudio",
        input_event=event,
    )


def make_request(
    *,
    execution_mode: str = LMSTUDIO_MODE,
    model: str | None = "local-model",
    provider_options: dict | None = None,
) -> LocalTurnRequestEnvelope:
    return LocalTurnRequestEnvelope(
        schema_version="0.1.1-draft",
        execution_mode=execution_mode,
        assistant_turn_input=make_turn_input(),
        model=model,
        instructions="Use the loaded local model.",
        previous_response_id="previous-local-api-lmstudio",
        provider_options={} if provider_options is None else provider_options,
    )


def make_payload(*, trace_id: str = "trace-local-api-lmstudio") -> dict:
    return {
        "schema_version": "0.1.1-draft",
        "execution_mode": LMSTUDIO_MODE,
        "assistant_turn_input": {
            "schema_version": "0.1.1-draft",
            "trace_id": trace_id,
            "turn_id": "turn-local-api-lmstudio",
            "input_event_id": "event-local-api-lmstudio",
            "session_ref": None,
            "identity_ref": None,
            "user_visible_input": "Hello through local API LM Studio",
            "assistant_mode": "default",
            "policy_context": {
                "requested_capabilities": [],
                "sensitivity": "normal",
            },
            "metadata": {},
        },
        "model": "local-model",
        "instructions": "Use the loaded local model.",
        "previous_response_id": "previous-local-api-lmstudio",
        "provider_options": {},
    }


def success_result(turn_input) -> AssistantTurnResult:
    return AssistantTurnResult(
        schema_version="0.1.1-draft",
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        assistant_final_response={
            "schema_version": "0.1.1-draft",
            "response_type": "text",
            "text": "LM Studio local API response.",
            "payload_ref": None,
            "output_channel_intent": "default",
            "safe_for_display": True,
            "safe_for_speech": True,
            "memory_write_candidate_hint": False,
            "finish_reason": "stop",
            "metadata": {},
        },
        output_events=[],
        stage_summaries=[],
        provider_turn_refs=[
            {
                "ref_type": "provider_turn",
                "ref_id": "lmstudio-response-001",
                "stage_name": "provider_stage",
                "provider_name": "lmstudio_responses",
                "status": "completed",
                "trace_id": turn_input.trace_id,
            }
        ],
        tool_result_refs=[],
        memory_result_refs=[],
        session_result_ref=None,
        error=None,
        metadata={},
    )


def call_app(
    app,
    path: str = "/v1/turns",
    *,
    method: str = "POST",
    body: object | None = None,
    auth: str | None = f"Bearer {EXPECTED_TOKEN}",
) -> tuple[str, dict]:
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = method
    environ["PATH_INFO"] = path
    if auth is not None:
        environ["HTTP_AUTHORIZATION"] = auth
    body_bytes = b"" if body is None else json.dumps(body).encode("utf-8")
    environ["CONTENT_LENGTH"] = str(len(body_bytes))
    environ["wsgi.input"] = BytesIO(body_bytes)
    captured: dict[str, object] = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status

    response_body = b"".join(app(environ, start_response)).decode("utf-8")
    return captured["status"], json.loads(response_body)


def test_lmstudio_handler_rejects_unsupported_execution_mode():
    from packages.runtime_composition.local_api_lmstudio_turns import (
        create_local_api_lmstudio_turn_handler,
    )

    result = create_local_api_lmstudio_turn_handler()(
        make_request(execution_mode="assistant_runtime_fake_provider")
    )

    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.code == ErrorCode.VALIDATION_ERROR
    assert result.error.details == {"reason": "unsupported_execution_mode"}


def test_lmstudio_handler_rejects_missing_or_empty_model():
    from packages.runtime_composition.local_api_lmstudio_turns import (
        create_local_api_lmstudio_turn_handler,
    )

    handler = create_local_api_lmstudio_turn_handler()

    missing = handler(make_request(model=None))
    empty = handler(make_request(model=" "))

    assert missing.error is not None
    assert missing.error.code == ErrorCode.VALIDATION_ERROR
    assert missing.error.details == {"reason": "invalid_model"}
    assert empty.error is not None
    assert empty.error.code == ErrorCode.VALIDATION_ERROR
    assert empty.error.details == {"reason": "invalid_model"}


def test_lmstudio_handler_rejects_provider_options():
    from packages.runtime_composition.local_api_lmstudio_turns import (
        create_local_api_lmstudio_turn_handler,
    )

    result = create_local_api_lmstudio_turn_handler()(
        make_request(provider_options={"temperature": 0})
    )

    assert result.error is not None
    assert result.error.code == ErrorCode.VALIDATION_ERROR
    assert result.error.details == {"reason": "invalid_provider_options"}


def test_lmstudio_handler_calls_runtime_composition_bridge(monkeypatch):
    import packages.runtime_composition.local_api_lmstudio_turns as lmstudio_turns

    captured = {}

    def fake_bridge(turn_input, **kwargs):
        captured["turn_input"] = turn_input
        captured["kwargs"] = kwargs
        return success_result(turn_input)

    monkeypatch.setattr(
        lmstudio_turns,
        "run_lmstudio_responses_assistant_bridge",
        fake_bridge,
    )
    sink = object()

    result = lmstudio_turns.create_local_api_lmstudio_turn_handler(
        telemetry_sink=sink
    )(make_request())

    assert result.error is None
    assert result.assistant_final_response.text == "LM Studio local API response."
    assert captured["turn_input"].trace_id == "trace-local-api-lmstudio"
    assert captured["kwargs"] == {
        "model": "local-model",
        "instructions": "Use the loaded local model.",
        "previous_response_id": "previous-local-api-lmstudio",
        "provider_options": {},
        "telemetry_sink": sink,
    }


def test_lmstudio_handler_preserves_provider_stage_error_results(monkeypatch):
    import packages.runtime_composition.local_api_lmstudio_turns as lmstudio_turns

    from tests.integration.test_runtime_composition_real_provider_bridge import (
        RecordingProvider,
        provider_error_response,
    )

    import packages.runtime_composition.assistant_provider_bridge as bridge

    monkeypatch.setattr(
        bridge,
        "create_provider",
        lambda config: RecordingProvider(provider_error_response()),
    )

    result = lmstudio_turns.create_local_api_lmstudio_turn_handler()(make_request())
    serialized = json.dumps(result.model_dump())

    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.code == ErrorCode.PROVIDER_ERROR
    assert "must-not-leak" not in serialized


def test_lmstudio_handler_maps_provider_exception_failures(monkeypatch):
    import packages.runtime_composition.local_api_lmstudio_turns as lmstudio_turns
    import packages.runtime_composition.assistant_provider_bridge as bridge

    cases = [
        (ConnectionError("secret connection details"), ErrorCode.PROVIDER_UNAVAILABLE),
        (TimeoutError("secret timeout details"), ErrorCode.PROVIDER_TIMEOUT),
        (RuntimeError("secret provider details"), ErrorCode.PROVIDER_ERROR),
    ]

    for exc, expected_code in cases:
        monkeypatch.setattr(
            bridge,
            "create_provider",
            lambda _config, exc=exc: RaisingProvider(exc),
        )

        result = lmstudio_turns.create_local_api_lmstudio_turn_handler()(make_request())
        serialized = json.dumps(result.model_dump())

        assert result.assistant_final_response is None
        assert result.error is not None
        assert result.error.code == expected_code
        assert "secret" not in serialized


def test_lmstudio_handler_preserves_empty_output_error(monkeypatch):
    import packages.runtime_composition.local_api_lmstudio_turns as lmstudio_turns
    import packages.runtime_composition.assistant_provider_bridge as bridge
    from tests.integration.test_runtime_composition_real_provider_bridge import (
        RecordingProvider,
        empty_response,
    )

    monkeypatch.setattr(
        bridge,
        "create_provider",
        lambda config: RecordingProvider(empty_response()),
    )

    result = lmstudio_turns.create_local_api_lmstudio_turn_handler()(make_request())
    serialized = json.dumps(result.model_dump())

    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.code == ErrorCode.VALIDATION_ERROR
    assert result.error.message == "Provider output was empty."
    assert "must-not-leak" not in serialized


def test_lmstudio_malformed_provider_response_maps_to_safe_local_api_error(
    monkeypatch,
):
    import packages.runtime_composition.assistant_provider_bridge as bridge
    from packages.runtime_composition.local_api_lmstudio_turns import (
        create_local_api_lmstudio_turn_handler,
    )
    from tests.local_api.test_turns_api import make_provider

    monkeypatch.setattr(
        bridge,
        "create_provider",
        lambda config: MalformedProvider(),
    )
    app = create_health_version_api_app(
        make_provider(),
        turn_handler=create_local_api_lmstudio_turn_handler(),
        local_auth_token=EXPECTED_TOKEN,
        accepted_turn_execution_modes=(
            LOCAL_TURNS_LMSTUDIO_RESPONSES_EXECUTION_MODE,
        ),
    )

    status, payload = call_app(app, body=make_payload())
    serialized = json.dumps(payload)

    assert status == "500 Internal Server Error"
    assert payload["code"] == ErrorCode.INTERNAL_ERROR.value
    assert payload["message"] == "Local API turn handler failed."
    assert "object" not in serialized
    assert EXPECTED_TOKEN not in serialized


def test_lmstudio_runner_injects_handler_and_trace_reader(monkeypatch):
    import packages.runtime_composition.local_api_lmstudio_responses_runner as runner

    captured: dict[str, object] = {}
    server = RecordingServer()

    def fake_handler_factory(*, telemetry_sink=None):
        captured["telemetry_sink"] = telemetry_sink

        def handle(request):
            telemetry_sink.emit(
                make_trace_event(
                    schema_version=request.assistant_turn_input.schema_version,
                    trace_id=request.assistant_turn_input.trace_id,
                    turn_id=request.assistant_turn_input.turn_id,
                    stage=TraceStage.TURN_COMPLETED,
                    level=TraceLevel.INFO,
                    message="Manual smoke LM Studio turn completed.",
                    data={
                        "status": "success",
                        "provider_response_id": "must-not-appear",
                    },
                )
            )
            return success_result(request.assistant_turn_input)

        return handle

    def server_factory(host, port, app):
        captured["host"] = host
        captured["port"] = port
        captured["app"] = app
        return server

    monkeypatch.setattr(
        runner,
        "create_local_api_lmstudio_turn_handler",
        fake_handler_factory,
    )

    exit_code = runner.run_local_lmstudio_responses_api(
        dev_token=EXPECTED_TOKEN,
        server_factory=server_factory,
    )

    turn_status, turn_payload = call_app(captured["app"], body=make_payload())
    trace_status, trace_payload = call_app(
        captured["app"],
        "/v1/traces/trace-local-api-lmstudio",
        method="GET",
    )
    serialized_trace = json.dumps(trace_payload)

    assert exit_code == 0
    assert server.served is True
    assert server.closed is True
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8765
    assert captured["telemetry_sink"] is not None
    assert turn_status == "200 OK"
    assert AssistantTurnResult.model_validate(turn_payload).trace_id == (
        "trace-local-api-lmstudio"
    )
    assert trace_status == "200 OK"
    assert trace_payload["scope"] == "current_process"
    assert trace_payload["source"] == "in_memory"
    assert trace_payload["event_count"] >= 1
    assert "data" not in trace_payload["events"][0]
    assert "provider_response_id" not in serialized_trace
    assert "must-not-appear" not in serialized_trace


def test_lmstudio_runner_rejects_blank_dev_token_before_starting():
    from packages.runtime_composition.local_api_lmstudio_responses_runner import (
        run_local_lmstudio_responses_api,
    )

    def server_factory(_host, _port, _app):
        raise AssertionError("server must not start without a dev token")

    try:
        run_local_lmstudio_responses_api(
            dev_token=" ",
            server_factory=server_factory,
        )
    except ValueError as exc:
        assert str(exc) == "dev_token must be a non-empty fake/dev-only token"
    else:
        raise AssertionError("blank dev token must be rejected")
