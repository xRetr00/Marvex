from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from wsgiref.util import setup_testing_defaults

from packages.contracts import AssistantTurnResult, ErrorCode, ErrorEnvelope
from packages.process_runtime import HealthVersionProvider, ProcessRuntimeConfig


EXPECTED_TOKEN = "fake-local-token"


class RaisingInput:
    def read(self, *_args, **_kwargs):
        raise AssertionError("body was read before auth passed")


class RecordingServer:
    def __init__(self) -> None:
        self.served = False
        self.closed = False

    def serve_forever(self) -> None:
        self.served = True

    def server_close(self) -> None:
        self.closed = True


def make_provider() -> HealthVersionProvider:
    started_at = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
    return HealthVersionProvider(
        ProcessRuntimeConfig(
            service_name="marvex-local-api",
            service_version="0.1.0",
            started_at=started_at,
            clock=lambda: started_at + timedelta(seconds=11),
            contract_versions={
                "HealthCheck": "0.1.1-draft",
                "VersionInfo": "0.1.1-draft",
            },
            build={"version": "0.1.0"},
            dependencies={},
        )
    )


def make_request_payload(*, previous_response_id: str | None = None) -> dict:
    return {
        "schema_version": "0.1.1-draft",
        "execution_mode": "assistant_runtime_fake_provider",
        "assistant_turn_input": {
            "schema_version": "0.1.1-draft",
            "trace_id": "trace-local-api-composed",
            "turn_id": "turn-local-api-composed",
            "input_event_id": "event-local-api-composed",
            "session_ref": None,
            "identity_ref": None,
            "user_visible_input": "Hello through local API",
            "assistant_mode": "default",
            "policy_context": {
                "requested_capabilities": [],
                "sensitivity": "normal",
            },
            "metadata": {},
        },
        "model": "fake-model",
        "instructions": "Use fake provider.",
        "previous_response_id": previous_response_id,
        "provider_options": {},
    }


def make_app(handler):
    from packages.local_api import create_health_version_api_app

    return create_health_version_api_app(
        make_provider(),
        turn_handler=handler,
        local_auth_token=EXPECTED_TOKEN,
    )


def call_app(
    app,
    *,
    body: object | None = None,
    auth: str | None = f"Bearer {EXPECTED_TOKEN}",
) -> tuple[str, dict[str, str], dict]:
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = "POST"
    environ["PATH_INFO"] = "/v1/turns"
    if auth is not None:
        environ["HTTP_AUTHORIZATION"] = auth
    if body is None:
        body_bytes = b""
    else:
        body_bytes = json.dumps(body).encode("utf-8")
    environ["CONTENT_LENGTH"] = str(len(body_bytes))
    environ["wsgi.input"] = BytesIO(body_bytes)
    captured: dict[str, object] = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status
        captured["headers"] = dict(headers)

    response_body = b"".join(app(environ, start_response)).decode("utf-8")
    return captured["status"], captured["headers"], json.loads(response_body)


def call_app_without_readable_body(app) -> tuple[str, dict[str, str], dict]:
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = "POST"
    environ["PATH_INFO"] = "/v1/turns"
    environ["CONTENT_LENGTH"] = "50"
    environ["wsgi.input"] = RaisingInput()
    captured: dict[str, object] = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status
        captured["headers"] = dict(headers)

    response_body = b"".join(app(environ, start_response)).decode("utf-8")
    return captured["status"], captured["headers"], json.loads(response_body)


def test_fake_turn_handler_factory_calls_runtime_composition_bridge(monkeypatch):
    import packages.runtime_composition.local_api_fake_turns as fake_turns

    captured = {}

    def fake_bridge(turn_input, **kwargs):
        captured["turn_input"] = turn_input
        captured["kwargs"] = kwargs
        return AssistantTurnResult(
            schema_version="0.1.1-draft",
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            assistant_final_response={
                "schema_version": "0.1.1-draft",
                "response_type": "text",
                "text": "bridge response",
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
            provider_turn_refs=[],
            tool_result_refs=[],
            memory_result_refs=[],
            session_result_ref=None,
            error=None,
            metadata={},
        )

    monkeypatch.setattr(fake_turns, "run_fake_provider_assistant_bridge", fake_bridge)

    handler = fake_turns.create_local_api_fake_turn_handler()
    status, _headers, payload = call_app(
        make_app(handler),
        body=make_request_payload(previous_response_id="previous-local-api"),
    )

    result = AssistantTurnResult.model_validate(payload)
    assert status == "200 OK"
    assert result.assistant_final_response.text == "bridge response"
    assert captured["turn_input"].trace_id == "trace-local-api-composed"
    assert captured["turn_input"].turn_id == "turn-local-api-composed"
    assert captured["kwargs"] == {
        "model": "fake-model",
        "instructions": "Use fake provider.",
        "previous_response_id": "previous-local-api",
        "provider_options": {},
    }


def test_local_api_with_fake_handler_executes_fake_provider_path():
    from packages.runtime_composition import create_local_api_fake_turn_handler

    status, _headers, payload = call_app(
        make_app(create_local_api_fake_turn_handler()),
        body=make_request_payload(previous_response_id="previous-local-api"),
    )

    result = AssistantTurnResult.model_validate(payload)
    assert status == "200 OK"
    assert result.error is None
    assert result.trace_id == "trace-local-api-composed"
    assert result.turn_id == "turn-local-api-composed"
    assert result.assistant_final_response.text == "fake provider response"
    assert result.provider_turn_refs[0].provider_name == "fake"
    assert result.provider_turn_refs[0].ref_id == "fake-response-001"
    assert "provider_response_id" not in payload


def test_local_api_auth_failure_does_not_call_composed_fake_handler(monkeypatch):
    import packages.runtime_composition.local_api_fake_turns as fake_turns

    called = {"value": False}

    def fake_bridge(*_args, **_kwargs):
        called["value"] = True
        raise AssertionError("handler must not run without auth")

    monkeypatch.setattr(fake_turns, "run_fake_provider_assistant_bridge", fake_bridge)

    status, _headers, payload = call_app_without_readable_body(
        make_app(fake_turns.create_local_api_fake_turn_handler())
    )

    error = ErrorEnvelope.model_validate(payload)
    assert status == "401 Unauthorized"
    assert error.code == ErrorCode.AUTH_REQUIRED
    assert called["value"] is False
    assert EXPECTED_TOKEN not in json.dumps(payload)


def test_fake_turns_smoke_runner_injects_runtime_composition_handler(monkeypatch):
    import packages.runtime_composition.local_api_fake_turns_runner as smoke_runner

    captured: dict[str, object] = {}
    server = RecordingServer()

    def fake_handler_factory():
        captured["factory_called"] = True

        def handle(request):
            captured["request"] = request
            return AssistantTurnResult(
                schema_version="0.1.1-draft",
                trace_id=request.assistant_turn_input.trace_id,
                turn_id=request.assistant_turn_input.turn_id,
                assistant_final_response={
                    "schema_version": "0.1.1-draft",
                    "response_type": "text",
                    "text": "manual smoke bridge response",
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
                provider_turn_refs=[],
                tool_result_refs=[],
                memory_result_refs=[],
                session_result_ref=None,
                error=None,
                metadata={},
            )

        return handle

    def server_factory(host, port, app):
        captured["host"] = host
        captured["port"] = port
        captured["app"] = app
        return server

    monkeypatch.setattr(
        smoke_runner,
        "create_local_api_fake_turn_handler",
        fake_handler_factory,
    )

    exit_code = smoke_runner.run_local_fake_turns_api(
        dev_token=EXPECTED_TOKEN,
        server_factory=server_factory,
    )

    status, _headers, payload = call_app(
        captured["app"],
        body=make_request_payload(previous_response_id="previous-smoke"),
    )

    result = AssistantTurnResult.model_validate(payload)
    assert exit_code == 0
    assert server.served is True
    assert server.closed is True
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8765
    assert captured["factory_called"] is True
    assert captured["request"].previous_response_id == "previous-smoke"
    assert status == "200 OK"
    assert result.assistant_final_response.text == "manual smoke bridge response"


def test_fake_turns_smoke_runner_rejects_blank_dev_token_before_starting():
    import packages.runtime_composition.local_api_fake_turns_runner as smoke_runner

    def server_factory(_host, _port, _app):
        raise AssertionError("server must not start without a dev token")

    try:
        smoke_runner.run_local_fake_turns_api(
            dev_token=" ",
            server_factory=server_factory,
        )
    except ValueError as exc:
        assert str(exc) == "dev_token must be a non-empty fake/dev-only token"
    else:
        raise AssertionError("blank dev token must be rejected")
