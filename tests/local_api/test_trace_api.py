from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from packages.contracts import (
    AssistantTurnResult,
    ErrorCode,
    ErrorEnvelope,
    HealthCheck,
    VersionInfo,
)
from packages.local_api import create_local_api_asgi_app
from packages.process_runtime import HealthVersionProvider, ProcessRuntimeConfig
from tests.local_api.asgi_helpers import asgi_call

from tests.local_api.test_turns_api import (
    EXPECTED_TOKEN,
    RecordingHandler,
    make_request_payload,
)


class RecordingTraceReader:
    def __init__(self, envelope: dict | None = None):
        self.envelope = envelope
        self.requests: list[str] = []

    def read_trace(self, trace_id: str):
        self.requests.append(trace_id)
        return self.envelope


class ExplodingTraceReader:
    def __init__(self):
        self.requests: list[str] = []

    def read_trace(self, trace_id: str):
        self.requests.append(trace_id)
        raise RuntimeError("trace reader exploded with token secret")


class NonJsonTraceReader:
    def read_trace(self, trace_id: str):
        return {"trace_id": trace_id, "bad": object()}


def make_provider() -> HealthVersionProvider:
    started_at = datetime(2026, 5, 15, 12, 0, tzinfo=UTC)
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


def make_trace_envelope(trace_id: str = "trace-reader-test") -> dict:
    return {
        "schema_version": "0.1.1-draft",
        "trace_id": trace_id,
        "scope": "current_process",
        "source": "in_memory",
        "events": [
            {
                "trace_id": trace_id,
                "turn_id": "turn-reader-test",
                "event_id": "event-001",
                "timestamp": "2026-05-15T09:30:00Z",
                "stage": "turn_completed",
                "level": "info",
                "message": "Turn completed.",
                "status": "completed",
                "usage": {"total_count": 2},
            }
        ],
        "event_count": 1,
        "truncated": False,
    }


def make_app(*, trace_reader=None, turn_handler=None, token: str | None = EXPECTED_TOKEN):
    return create_local_api_asgi_app(
        make_provider(),
        turn_handler=turn_handler,
        trace_reader=trace_reader,
        local_auth_token=token,
    )


def call_app(
    app,
    path: str,
    *,
    method: str = "GET",
    body: object = None,
    auth: str | None = None,
) -> tuple[str, dict[str, str], dict]:
    return asgi_call(app, path, method=method, body=body, auth=auth)


def test_health_and_version_remain_public_with_trace_reader_configured():
    reader = RecordingTraceReader()
    app = make_app(trace_reader=reader)

    health_status, _headers, health_payload = call_app(app, "/health")
    version_status, _headers, version_payload = call_app(app, "/version")

    assert health_status == "200 OK"
    assert HealthCheck.model_validate(health_payload).service == "marvex-local-api"
    assert version_status == "200 OK"
    assert VersionInfo.model_validate(version_payload).service_version == "0.1.0"
    assert reader.requests == []


def test_turns_behavior_remains_unchanged_with_trace_reader_configured():
    handler = RecordingHandler()

    status, _headers, payload = call_app(
        make_app(trace_reader=RecordingTraceReader(), turn_handler=handler),
        "/v1/turns",
        method="POST",
        body=make_request_payload(),
        auth="Bearer fake-local-token",
    )

    result = AssistantTurnResult.model_validate(payload)
    assert status == "200 OK"
    assert result.trace_id == "trace-turns-test"
    assert len(handler.requests) == 1


def test_trace_route_rejects_missing_auth_before_reader_lookup():
    reader = RecordingTraceReader(make_trace_envelope())

    status, _headers, payload = call_app(
        make_app(trace_reader=reader),
        "/v1/traces/trace-reader-test",
    )

    error = ErrorEnvelope.model_validate(payload)
    assert status == "401 Unauthorized"
    assert error.code == ErrorCode.AUTH_REQUIRED
    assert error.details["reason"] == "missing"
    assert reader.requests == []


def test_trace_route_rejects_malformed_and_wrong_auth_before_reader_lookup():
    reader = RecordingTraceReader(make_trace_envelope())

    malformed_status, _headers, malformed_payload = call_app(
        make_app(trace_reader=reader),
        "/v1/traces/trace-reader-test",
        auth="Token fake-local-token",
    )
    wrong_status, _headers, wrong_payload = call_app(
        make_app(trace_reader=reader),
        "/v1/traces/trace-reader-test",
        auth="Bearer wrong-token",
    )

    assert malformed_status == "401 Unauthorized"
    assert ErrorEnvelope.model_validate(malformed_payload).code == ErrorCode.AUTH_REQUIRED
    assert wrong_status == "401 Unauthorized"
    assert ErrorEnvelope.model_validate(wrong_payload).code == ErrorCode.AUTH_REQUIRED
    assert "fake-local-token" not in json.dumps(malformed_payload)
    assert "wrong-token" not in json.dumps(wrong_payload)
    assert reader.requests == []


def test_trace_route_rejects_invalid_trace_id_without_lookup_after_auth():
    reader = RecordingTraceReader(make_trace_envelope())

    status, _headers, payload = call_app(
        make_app(trace_reader=reader),
        "/v1/traces/trace%20secret",
        auth="Bearer fake-local-token",
    )

    error = ErrorEnvelope.model_validate(payload)
    assert status == "400 Bad Request"
    assert error.code == ErrorCode.VALIDATION_ERROR
    assert error.details["reason"] == "invalid_trace_id"
    assert reader.requests == []


def test_trace_route_rejects_empty_trace_id_without_lookup_after_auth():
    reader = RecordingTraceReader(make_trace_envelope())

    status, _headers, payload = call_app(
        make_app(trace_reader=reader),
        "/v1/traces/",
        auth="Bearer fake-local-token",
    )

    error = ErrorEnvelope.model_validate(payload)
    assert status == "400 Bad Request"
    assert error.code == ErrorCode.VALIDATION_ERROR
    assert error.details["reason"] == "invalid_trace_id"
    assert reader.requests == []


def test_trace_route_returns_not_found_for_unknown_trace_id():
    reader = RecordingTraceReader(None)

    status, _headers, payload = call_app(
        make_app(trace_reader=reader),
        "/v1/traces/trace-missing",
        auth="Bearer fake-local-token",
    )

    error = ErrorEnvelope.model_validate(payload)
    assert status == "404 Not Found"
    assert error.code == ErrorCode.NOT_FOUND
    assert error.details == {"reason": "trace_not_found"}
    assert reader.requests == ["trace-missing"]


def test_trace_route_returns_safe_injected_trace_envelope():
    reader = RecordingTraceReader(make_trace_envelope())

    status, headers, payload = call_app(
        make_app(trace_reader=reader),
        "/v1/traces/trace-reader-test",
        auth="Bearer fake-local-token",
    )

    assert status == "200 OK"
    assert headers["Content-Type"] == "application/json"
    assert payload == make_trace_envelope()
    assert reader.requests == ["trace-reader-test"]


def test_trace_route_never_exposes_raw_trace_data_or_provider_response_id():
    from packages.contracts import TraceLevel, TraceStage
    from packages.telemetry import InMemoryTraceReader, make_trace_event

    reader = InMemoryTraceReader()
    reader.emit(
        make_trace_event(
            schema_version="0.1.1-draft",
            trace_id="trace-reader-test",
            turn_id="turn-reader-test",
            stage=TraceStage.TURN_COMPLETED,
            level=TraceLevel.INFO,
            message="Turn completed.",
            data={
                "prompt": "raw prompt",
                "raw_provider_output": "provider payload",
                "provider_response_id": "provider-response-secret",
                "status": "completed",
            },
        )
    )

    status, _headers, payload = call_app(
        make_app(trace_reader=reader),
        "/v1/traces/trace-reader-test",
        auth="Bearer fake-local-token",
    )

    serialized = json.dumps(payload)
    assert status == "200 OK"
    assert "data" not in payload["events"][0]
    assert "provider_response_id" not in payload["events"][0]
    assert "raw prompt" not in serialized
    assert "provider payload" not in serialized
    assert "provider-response-secret" not in serialized


def test_trace_reader_failure_maps_to_safe_error_without_token_or_details():
    reader = ExplodingTraceReader()

    status, _headers, payload = call_app(
        make_app(trace_reader=reader),
        "/v1/traces/trace-reader-test",
        auth="Bearer fake-local-token",
    )

    error = ErrorEnvelope.model_validate(payload)
    serialized = json.dumps(payload)
    assert status == "500 Internal Server Error"
    assert error.code == ErrorCode.INTERNAL_ERROR
    assert error.message == "Local API trace reader failed."
    assert "trace reader exploded" not in serialized
    assert "token secret" not in serialized
    assert "fake-local-token" not in serialized


def test_trace_reader_non_json_envelope_maps_to_safe_error():
    status, _headers, payload = call_app(
        make_app(trace_reader=NonJsonTraceReader()),
        "/v1/traces/trace-reader-test",
        auth="Bearer fake-local-token",
    )

    error = ErrorEnvelope.model_validate(payload)
    serialized = json.dumps(payload)
    assert status == "500 Internal Server Error"
    assert error.code == ErrorCode.INTERNAL_ERROR
    assert error.message == "Local API trace reader failed."
    assert "object at" not in serialized
    assert "fake-local-token" not in serialized


def test_trace_route_without_injected_reader_returns_service_unhealthy():
    status, _headers, payload = call_app(
        make_app(trace_reader=None),
        "/v1/traces/trace-reader-test",
        auth="Bearer fake-local-token",
    )

    error = ErrorEnvelope.model_validate(payload)
    assert status == "503 Service Unavailable"
    assert error.code == ErrorCode.SERVICE_UNHEALTHY
    assert error.details == {"reason": "trace_reader_unavailable"}
