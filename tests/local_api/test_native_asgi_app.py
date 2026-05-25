from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

from packages.process_runtime import HealthVersionProvider, ProcessRuntimeConfig
from tests.local_api.test_trace_api import RecordingTraceReader, make_trace_envelope
from tests.local_api.test_turns_api import EXPECTED_TOKEN, RecordingHandler, make_request_payload


def _provider() -> HealthVersionProvider:
    started_at = datetime(2026, 5, 25, 12, 0, tzinfo=UTC)
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


def test_local_api_native_asgi_health_version_turns_and_trace_contracts() -> None:
    from packages.local_api.asgi_app import create_local_api_asgi_app

    handler = RecordingHandler()
    reader = RecordingTraceReader(make_trace_envelope("trace-native-asgi"))
    client = TestClient(
        create_local_api_asgi_app(
            _provider(),
            turn_handler=handler,
            trace_reader=reader,
            local_auth_token=EXPECTED_TOKEN,
        )
    )

    health = client.get("/health")
    version = client.get("/version")
    turn = client.post(
        "/v1/turns",
        headers={"Authorization": f"Bearer {EXPECTED_TOKEN}"},
        json=make_request_payload(),
    )
    trace = client.get(
        "/v1/traces/trace-native-asgi",
        headers={"Authorization": f"Bearer {EXPECTED_TOKEN}"},
    )

    assert health.status_code == 200
    assert health.json()["uptime_seconds"] == 11
    assert version.status_code == 200
    assert version.json()["service_version"] == "0.1.0"
    assert turn.status_code == 200
    assert turn.json()["trace_id"] == "trace-turns-test"
    assert len(handler.requests) == 1
    assert trace.status_code == 200
    assert trace.json()["trace_id"] == "trace-native-asgi"
    assert reader.requests == ["trace-native-asgi"]


def test_local_api_native_asgi_protected_routes_reject_missing_auth_before_body_read() -> None:
    from packages.local_api.asgi_app import create_local_api_asgi_app

    handler = RecordingHandler()
    client = TestClient(
        create_local_api_asgi_app(
            _provider(),
            turn_handler=handler,
            local_auth_token=EXPECTED_TOKEN,
        )
    )

    response = client.post("/v1/turns", content=b"not-json")

    assert response.status_code == 401
    assert response.json()["details"]["reason"] == "missing"
    assert handler.requests == []
