import json
import threading
from datetime import UTC, datetime, timedelta
from wsgiref.simple_server import make_server

from packages.process_runtime import HealthVersionProvider, ProcessRuntimeConfig
from tests.local_api.test_trace_api import RecordingTraceReader, make_trace_envelope
from tests.local_api.test_turns_api import RecordingHandler, make_request_payload


def make_provider() -> HealthVersionProvider:
    started_at = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)
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


def safe_discovery_payload(port: int) -> dict:
    return {
        "schema_version": "0.1.1-draft",
        "service": "marvex-local-api",
        "base_url": f"http://127.0.0.1:{port}",
        "bind_host": "127.0.0.1",
        "port": port,
        "auth_required": True,
        "auth_token_present": True,
        "token_value_logged": False,
        "discovery_mode": "future_local_file",
        "discovery_file_path": None,
        "process_id": 123,
        "started_at": "2026-05-16T00:00:00Z",
        "contract_versions": {"LocalApiStartup": "0.1.1-draft"},
        "warnings": [],
    }


def test_client_uses_discovery_metadata_to_call_loopback_local_api(tmp_path):
    from packages.local_api import create_health_version_api_app
    from packages.local_api_client import load_local_api_client_from_discovery

    app = create_health_version_api_app(
        make_provider(),
        turn_handler=RecordingHandler(),
        trace_reader=RecordingTraceReader(make_trace_envelope("trace-client-test")),
        local_auth_token="fake-local-token",
    )
    httpd = make_server("127.0.0.1", 0, app)
    port = httpd.server_port
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    discovery_file = tmp_path / "marvex" / "local-api.json"
    discovery_file.parent.mkdir(parents=True)
    discovery_file.write_text(
        json.dumps(safe_discovery_payload(port)),
        encoding="utf-8",
    )

    try:
        client = load_local_api_client_from_discovery(
            discovery_file_path=str(discovery_file),
            local_user_root=tmp_path,
        )

        health = client.get_health()
        turn = client.post_turn(
            make_request_payload(assistant_turn_input={
                **make_request_payload()["assistant_turn_input"],
                "trace_id": "trace-client-test",
            }),
            local_auth_token="fake-local-token",
        )
        trace = client.get_trace(
            "trace-client-test",
            local_auth_token="fake-local-token",
        )
    finally:
        httpd.shutdown()
        thread.join(timeout=5)
        httpd.server_close()

    assert health.status_code == 200
    assert health.body["service"] == "marvex-local-api"
    assert turn.status_code == 200
    assert turn.body["trace_id"] == "trace-client-test"
    assert trace.status_code == 200
    assert trace.body["scope"] == "current_process"
    serialized = json.dumps(trace.body)
    assert "fake-local-token" not in serialized
    assert "local_auth_token" not in serialized
