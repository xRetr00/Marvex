from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from wsgiref.util import setup_testing_defaults

from packages.contracts import (
    AssistantTurnResult,
    ErrorCode,
    ErrorEnvelope,
    HealthCheck,
    VersionInfo,
)
from packages.process_runtime import HealthVersionProvider, ProcessRuntimeConfig

EXPECTED_TOKEN = "fake-local-token"


class RecordingTurnHandler:
    def __init__(self) -> None:
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return AssistantTurnResult(
            schema_version="0.1.1-draft",
            trace_id=request.assistant_turn_input.trace_id,
            turn_id=request.assistant_turn_input.turn_id,
            assistant_final_response={
                "schema_version": "0.1.1-draft",
                "response_type": "text",
                "text": "manual runner stub response",
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


class RaisingInput:
    def read(self, *_args, **_kwargs):
        raise AssertionError("request body must not be read before auth passes")


def make_provider() -> HealthVersionProvider:
    started_at = datetime(2026, 5, 13, 12, 0, tzinfo=UTC)
    return HealthVersionProvider(
        ProcessRuntimeConfig(
            service_name="marvex-local-api",
            service_version="0.1.0",
            started_at=started_at,
            clock=lambda: started_at + timedelta(seconds=3),
            contract_versions={
                "HealthCheck": "0.1.1-draft",
                "VersionInfo": "0.1.1-draft",
            },
            build={"version": "0.1.0"},
            dependencies={},
        )
    )


def call_app(app, path: str) -> tuple[str, dict[str, str], dict]:
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = "GET"
    environ["PATH_INFO"] = path
    captured: dict[str, object] = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = b"".join(app(environ, start_response)).decode("utf-8")
    return captured["status"], captured["headers"], json.loads(body)


def make_turn_payload() -> dict:
    return {
        "schema_version": "0.1.1-draft",
        "execution_mode": "assistant_runtime_fake_provider",
        "assistant_turn_input": {
            "schema_version": "0.1.1-draft",
            "trace_id": "trace-manual-runner",
            "turn_id": "turn-manual-runner",
            "input_event_id": "event-manual-runner",
            "session_ref": None,
            "identity_ref": None,
            "user_visible_input": "Manual runner smoke",
            "assistant_mode": "default",
            "policy_context": {
                "requested_capabilities": [],
                "sensitivity": "normal",
            },
            "metadata": {},
        },
        "model": "fake-model",
        "instructions": None,
        "previous_response_id": None,
        "provider_options": {},
    }


def call_turns_app(
    app,
    *,
    body: object | None = None,
    auth: str | None = f"Bearer {EXPECTED_TOKEN}",
    unreadable_body: bool = False,
) -> tuple[str, dict[str, str], dict]:
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = "POST"
    environ["PATH_INFO"] = "/v1/turns"
    if auth is not None:
        environ["HTTP_AUTHORIZATION"] = auth
    if unreadable_body:
        environ["CONTENT_LENGTH"] = "99"
        environ["wsgi.input"] = RaisingInput()
    else:
        body_bytes = json.dumps(body or make_turn_payload()).encode("utf-8")
        environ["CONTENT_LENGTH"] = str(len(body_bytes))
        environ["wsgi.input"] = BytesIO(body_bytes)
    captured: dict[str, object] = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status
        captured["headers"] = dict(headers)

    response_body = b"".join(app(environ, start_response)).decode("utf-8")
    return captured["status"], captured["headers"], json.loads(response_body)


class RecordingServer:
    def __init__(self, *, interrupt: bool = False) -> None:
        self.interrupt = interrupt
        self.served = False
        self.closed = False

    def serve_forever(self) -> None:
        self.served = True
        if self.interrupt:
            raise KeyboardInterrupt

    def server_close(self) -> None:
        self.closed = True


def test_runner_config_defaults_to_loopback_only():
    from packages.local_api.runner import LocalApiConfig

    config = LocalApiConfig()

    assert config.host == "127.0.0.1"
    assert config.port == 8765


def test_runner_config_rejects_remote_bind_hosts():
    from packages.local_api.runner import LocalApiConfig

    try:
        LocalApiConfig(host="0.0.0.0")
    except ValueError as exc:
        assert str(exc) == "host must be loopback-only"
    else:
        raise AssertionError("remote Local API bind host must be rejected")


def test_runner_uses_existing_health_version_app_behavior():
    from packages.local_api.runner import run_local_health_version_api

    captured: dict[str, object] = {}
    server = RecordingServer()

    def server_factory(host, port, app):
        captured["host"] = host
        captured["port"] = port
        captured["app"] = app
        return server

    exit_code = run_local_health_version_api(
        provider=make_provider(),
        server_factory=server_factory,
    )

    assert exit_code == 0
    assert server.served is True
    assert server.closed is True
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8765

    health_status, _, health_payload = call_app(captured["app"], "/health")
    version_status, _, version_payload = call_app(captured["app"], "/version")
    missing_status, _, missing_payload = call_app(captured["app"], "/missing")

    health = HealthCheck.model_validate(health_payload)
    version = VersionInfo.model_validate(version_payload)
    error = ErrorEnvelope.model_validate(missing_payload)

    assert health_status == "200 OK"
    assert health.service == "marvex-local-api"
    assert health.uptime_seconds == 3
    assert version_status == "200 OK"
    assert version.service == "marvex-local-api"
    assert missing_status == "404 Not Found"
    assert error.source == "local_api"
    assert error.details == {"path": "/missing"}


def test_runner_can_inject_manual_turn_handler_and_fake_token():
    from packages.local_api.runner import run_local_health_version_api

    captured: dict[str, object] = {}
    server = RecordingServer()
    handler = RecordingTurnHandler()

    def server_factory(host, port, app):
        captured["host"] = host
        captured["port"] = port
        captured["app"] = app
        return server

    exit_code = run_local_health_version_api(
        provider=make_provider(),
        server_factory=server_factory,
        turn_handler=handler,
        local_auth_token=EXPECTED_TOKEN,
    )

    assert exit_code == 0
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8765

    status, _headers, payload = call_turns_app(captured["app"])

    result = AssistantTurnResult.model_validate(payload)
    assert status == "200 OK"
    assert result.trace_id == "trace-manual-runner"
    assert result.assistant_final_response.text == "manual runner stub response"
    assert len(handler.requests) == 1
    assert handler.requests[0].assistant_turn_input.turn_id == "turn-manual-runner"


def test_runner_injected_turn_handler_keeps_auth_before_body_behavior():
    from packages.local_api.runner import run_local_health_version_api

    captured: dict[str, object] = {}
    server = RecordingServer()
    handler = RecordingTurnHandler()

    def server_factory(host, port, app):
        captured["app"] = app
        return server

    run_local_health_version_api(
        provider=make_provider(),
        server_factory=server_factory,
        turn_handler=handler,
        local_auth_token=EXPECTED_TOKEN,
    )

    status, _headers, payload = call_turns_app(
        captured["app"],
        auth="Bearer wrong-token",
        unreadable_body=True,
    )

    error = ErrorEnvelope.model_validate(payload)
    assert status == "401 Unauthorized"
    assert error.code == ErrorCode.AUTH_REQUIRED
    assert "wrong-token" not in json.dumps(payload)
    assert handler.requests == []


def test_runner_handles_manual_interrupt_as_clean_stop():
    from packages.local_api.runner import run_local_health_version_api

    server = RecordingServer(interrupt=True)

    def server_factory(host, port, app):
        return server

    exit_code = run_local_health_version_api(
        provider=make_provider(),
        server_factory=server_factory,
    )

    assert exit_code == 0
    assert server.served is True
    assert server.closed is True


def test_default_runner_provider_uses_health_version_contracts():
    from packages.local_api.runner import create_default_health_version_provider

    started_at = datetime(2026, 5, 13, 12, 0, tzinfo=UTC)
    provider = create_default_health_version_provider(
        started_at=started_at,
        clock=lambda: started_at + timedelta(seconds=5),
    )

    health = provider.get_health()
    version = provider.get_version()

    assert health.schema_version == "0.1.1-draft"
    assert health.service == "marvex-local-api"
    assert health.version == "0.1.0"
    assert health.uptime_seconds == 5
    assert version.schema_version == "0.1.1-draft"
    assert version.service == "marvex-local-api"
    assert version.contract_versions == {
        "HealthCheck": "0.1.1-draft",
        "VersionInfo": "0.1.1-draft",
    }
