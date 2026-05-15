from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from io import BytesIO
from wsgiref.util import setup_testing_defaults

from packages.contracts import (
    AssistantFinalResponse,
    AssistantFinishReason,
    AssistantMode,
    AssistantResponseType,
    AssistantTurnInput,
    AssistantTurnResult,
    ErrorCode,
    ErrorEnvelope,
    HealthCheck,
    OutputChannelIntent,
    PolicyContext,
    Sensitivity,
    StageStatus,
    VersionInfo,
)
from packages.process_runtime import HealthVersionProvider, ProcessRuntimeConfig


EXPECTED_TOKEN = "fake-local-token"


class RaisingInput:
    def read(self, *_args, **_kwargs):
        raise AssertionError("request body must not be read before auth passes")


class RecordingHandler:
    def __init__(self):
        self.requests = []

    def __call__(self, request):
        self.requests.append(request)
        return make_result(request.assistant_turn_input)


class ExplodingHandler:
    def __call__(self, _request):
        raise RuntimeError("provider backend exploded with secret details")


def make_provider() -> HealthVersionProvider:
    started_at = datetime(2026, 5, 14, 12, 0, tzinfo=UTC)
    return HealthVersionProvider(
        ProcessRuntimeConfig(
            service_name="marvex-local-api",
            service_version="0.1.0",
            started_at=started_at,
            clock=lambda: started_at + timedelta(seconds=9),
            contract_versions={
                "HealthCheck": "0.1.1-draft",
                "VersionInfo": "0.1.1-draft",
            },
            build={"version": "0.1.0"},
            dependencies={},
        )
    )


def make_turn_input_payload() -> dict:
    return {
        "schema_version": "0.1.1-draft",
        "trace_id": "trace-turns-test",
        "turn_id": "turn-turns-test",
        "input_event_id": "event-turns-test",
        "session_ref": None,
        "identity_ref": None,
        "user_visible_input": "Hello",
        "assistant_mode": "default",
        "policy_context": {
            "requested_capabilities": [],
            "sensitivity": "normal",
        },
        "metadata": {},
    }


def make_request_payload(**overrides) -> dict:
    payload = {
        "schema_version": "0.1.1-draft",
        "execution_mode": "assistant_runtime_fake_provider",
        "assistant_turn_input": make_turn_input_payload(),
        "model": "fake-model",
        "instructions": None,
        "previous_response_id": None,
        "provider_options": {},
    }
    payload.update(overrides)
    return payload


def make_result(turn_input: AssistantTurnInput) -> AssistantTurnResult:
    return AssistantTurnResult(
        schema_version="0.1.1-draft",
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        assistant_final_response=AssistantFinalResponse(
            schema_version="0.1.1-draft",
            response_type=AssistantResponseType.TEXT,
            text="Stubbed local API response.",
            payload_ref=None,
            output_channel_intent=OutputChannelIntent.DEFAULT,
            safe_for_display=True,
            safe_for_speech=True,
            memory_write_candidate_hint=False,
            finish_reason=AssistantFinishReason.STOP,
            metadata={},
        ),
        output_events=[],
        stage_summaries=[],
        provider_turn_refs=[
            {
                "ref_type": "provider_turn",
                "ref_id": "fake-response-001",
                "stage_name": "provider_reasoning",
                "provider_name": "fake",
                "status": StageStatus.COMPLETED,
                "trace_id": turn_input.trace_id,
            }
        ],
        tool_result_refs=[],
        memory_result_refs=[],
        session_result_ref=None,
        error=None,
        metadata={},
    )


def make_app(
    handler=None,
    *,
    token: str | None = EXPECTED_TOKEN,
    accepted_turn_execution_modes=None,
):
    from packages.local_api import create_health_version_api_app

    kwargs = {
        "turn_handler": handler,
        "local_auth_token": token,
    }
    if accepted_turn_execution_modes is not None:
        kwargs["accepted_turn_execution_modes"] = accepted_turn_execution_modes
    return create_health_version_api_app(
        make_provider(),
        **kwargs,
    )


def call_app(
    app,
    path: str,
    *,
    method: str = "GET",
    body: object = None,
    auth: str | None = None,
) -> tuple[str, dict[str, str], dict]:
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = method
    environ["PATH_INFO"] = path
    if auth is not None:
        environ["HTTP_AUTHORIZATION"] = auth
    if body is None:
        body_bytes = b""
    elif isinstance(body, bytes):
        body_bytes = body
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


def call_app_without_readable_body(
    app,
    *,
    auth: str | None,
) -> tuple[str, dict[str, str], dict]:
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = "POST"
    environ["PATH_INFO"] = "/v1/turns"
    if auth is not None:
        environ["HTTP_AUTHORIZATION"] = auth
    environ["CONTENT_LENGTH"] = "99"
    environ["wsgi.input"] = RaisingInput()
    captured: dict[str, object] = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status
        captured["headers"] = dict(headers)

    response_body = b"".join(app(environ, start_response)).decode("utf-8")
    return captured["status"], captured["headers"], json.loads(response_body)


def test_health_remains_public_and_unchanged():
    status, _headers, payload = call_app(make_app(), "/health")

    health = HealthCheck.model_validate(payload)
    assert status == "200 OK"
    assert health.service == "marvex-local-api"
    assert health.status == "ok"
    assert health.uptime_seconds == 9


def test_version_remains_public_and_unchanged():
    status, _headers, payload = call_app(make_app(), "/version")

    version = VersionInfo.model_validate(payload)
    assert status == "200 OK"
    assert version.service == "marvex-local-api"
    assert version.service_version == "0.1.0"


def test_turns_rejects_missing_auth_before_body_read_or_handler_call():
    handler = RecordingHandler()

    status, _headers, payload = call_app_without_readable_body(
        make_app(handler),
        auth=None,
    )

    error = ErrorEnvelope.model_validate(payload)
    assert status == "401 Unauthorized"
    assert error.code == ErrorCode.AUTH_REQUIRED
    assert error.details["reason"] == "missing"
    assert handler.requests == []


def test_turns_rejects_malformed_auth_before_body_read_or_handler_call():
    handler = RecordingHandler()

    status, _headers, payload = call_app_without_readable_body(
        make_app(handler),
        auth="Token fake-local-token",
    )

    error = ErrorEnvelope.model_validate(payload)
    assert status == "401 Unauthorized"
    assert error.code == ErrorCode.AUTH_REQUIRED
    assert error.details["reason"] == "invalid"
    assert "fake-local-token" not in json.dumps(payload)
    assert handler.requests == []


def test_turns_rejects_wrong_auth_before_body_read_or_handler_call():
    handler = RecordingHandler()

    status, _headers, payload = call_app_without_readable_body(
        make_app(handler),
        auth="Bearer wrong-token",
    )

    error = ErrorEnvelope.model_validate(payload)
    assert status == "401 Unauthorized"
    assert error.code == ErrorCode.AUTH_REQUIRED
    assert error.details["reason"] == "invalid"
    assert "wrong-token" not in json.dumps(payload)
    assert handler.requests == []


def test_turns_rejects_invalid_json_only_after_valid_auth():
    handler = RecordingHandler()

    status, _headers, payload = call_app(
        make_app(handler),
        "/v1/turns",
        method="POST",
        body=b"{not-json",
        auth="Bearer fake-local-token",
    )

    error = ErrorEnvelope.model_validate(payload)
    assert status == "400 Bad Request"
    assert error.code == ErrorCode.VALIDATION_ERROR
    assert error.message == "Local API request validation failed."
    assert handler.requests == []


def test_turns_rejects_invalid_request_shape_only_after_valid_auth():
    handler = RecordingHandler()

    status, _headers, payload = call_app(
        make_app(handler),
        "/v1/turns",
        method="POST",
        body={"schema_version": "0.1.1-draft"},
        auth="Bearer fake-local-token",
    )

    error = ErrorEnvelope.model_validate(payload)
    assert status == "400 Bad Request"
    assert error.code == ErrorCode.VALIDATION_ERROR
    assert handler.requests == []


def test_turns_invokes_handler_once_with_validated_envelope():
    handler = RecordingHandler()

    status, _headers, payload = call_app(
        make_app(handler),
        "/v1/turns",
        method="POST",
        body=make_request_payload(previous_response_id="previous-response-001"),
        auth="Bearer fake-local-token",
    )

    result = AssistantTurnResult.model_validate(payload)
    assert status == "200 OK"
    assert result.trace_id == "trace-turns-test"
    assert len(handler.requests) == 1
    request = handler.requests[0]
    assert request.schema_version == "0.1.1-draft"
    assert request.execution_mode == "assistant_runtime_fake_provider"
    assert request.assistant_turn_input.trace_id == "trace-turns-test"
    assert request.model == "fake-model"
    assert request.instructions is None
    assert request.previous_response_id == "previous-response-001"
    assert request.provider_options == {}


def test_turns_can_accept_injected_lmstudio_execution_mode_without_changing_default():
    default_handler = RecordingHandler()
    lmstudio_handler = RecordingHandler()
    lmstudio_payload = make_request_payload(
        execution_mode="assistant_runtime_lmstudio_responses",
        model="local-model",
    )

    default_status, _headers, default_payload = call_app(
        make_app(default_handler),
        "/v1/turns",
        method="POST",
        body=lmstudio_payload,
        auth="Bearer fake-local-token",
    )
    injected_status, _headers, injected_payload = call_app(
        make_app(
            lmstudio_handler,
            accepted_turn_execution_modes=("assistant_runtime_lmstudio_responses",),
        ),
        "/v1/turns",
        method="POST",
        body=lmstudio_payload,
        auth="Bearer fake-local-token",
    )

    default_error = ErrorEnvelope.model_validate(default_payload)
    injected_result = AssistantTurnResult.model_validate(injected_payload)
    assert default_status == "400 Bad Request"
    assert default_error.code == ErrorCode.VALIDATION_ERROR
    assert default_error.details == {"reason": "unsupported_execution_mode"}
    assert default_handler.requests == []
    assert injected_status == "200 OK"
    assert injected_result.trace_id == "trace-turns-test"
    assert len(lmstudio_handler.requests) == 1
    assert (
        lmstudio_handler.requests[0].execution_mode
        == "assistant_runtime_lmstudio_responses"
    )
    assert lmstudio_handler.requests[0].model == "local-model"


def test_turns_serializes_successful_handler_result_as_assistant_turn_result():
    status, headers, payload = call_app(
        make_app(RecordingHandler()),
        "/v1/turns",
        method="POST",
        body=make_request_payload(),
        auth="Bearer fake-local-token",
    )

    result = AssistantTurnResult.model_validate(payload)
    assert status == "200 OK"
    assert headers["Content-Type"] == "application/json"
    assert result.assistant_final_response.text == "Stubbed local API response."
    assert result.provider_turn_refs[0].ref_id == "fake-response-001"
    assert "provider_response_id" not in payload


def test_turns_handler_failure_returns_safe_error_without_internal_details():
    status, _headers, payload = call_app(
        make_app(ExplodingHandler()),
        "/v1/turns",
        method="POST",
        body=make_request_payload(),
        auth="Bearer fake-local-token",
    )

    error = ErrorEnvelope.model_validate(payload)
    serialized = json.dumps(payload)
    assert status == "500 Internal Server Error"
    assert error.code == ErrorCode.INTERNAL_ERROR
    assert error.message == "Local API turn handler failed."
    assert error.source == "local_api"
    assert "provider backend exploded" not in serialized
    assert "secret details" not in serialized
    assert EXPECTED_TOKEN not in serialized


def test_unknown_routes_remain_safe_and_deterministic():
    status, _headers, payload = call_app(make_app(), "/missing")

    error = ErrorEnvelope.model_validate(payload)
    assert status == "404 Not Found"
    assert error.code == ErrorCode.NOT_FOUND
    assert error.details == {"path": "/missing"}
