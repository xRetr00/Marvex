from __future__ import annotations

import json
import subprocess
import sys
from io import BytesIO
from pathlib import Path
from wsgiref.util import setup_testing_defaults

from packages.contracts import (
    AssistantMode,
    AssistantTurnResult,
    ErrorCode,
    ErrorEnvelope,
    HealthCheck,
    HealthStatus,
    PolicyContext,
    Sensitivity,
    VersionInfo,
)


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "0.1.1-draft"
EXPECTED_TOKEN = "fake-core-service-entrypoint-token"


def _call_app(
    app,
    path: str,
    *,
    method: str = "GET",
    body: object | None = None,
    auth: str | None = None,
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

    def start_response(status, _headers, exc_info=None):
        captured["status"] = status

    response_body = b"".join(app(environ, start_response)).decode("utf-8")
    return str(captured["status"]), json.loads(response_body)


def _turn_payload(
    *,
    trace_id: str = "trace-core-entrypoint",
    turn_id: str = "turn-core-entrypoint",
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "execution_mode": "assistant_runtime_fake_provider",
        "assistant_turn_input": {
            "schema_version": SCHEMA_VERSION,
            "trace_id": trace_id,
            "turn_id": turn_id,
            "input_event_id": "event-core-entrypoint",
            "session_ref": None,
            "identity_ref": None,
            "user_visible_input": "Hello through the real Core service entrypoint",
            "assistant_mode": AssistantMode.DEFAULT.value,
            "policy_context": PolicyContext(
                requested_capabilities=[],
                sensitivity=Sensitivity.NORMAL,
            ).model_dump(mode="json"),
            "metadata": {},
        },
        "model": "fake-model",
        "instructions": None,
        "previous_response_id": None,
        "provider_options": {},
    }


def test_services_core_contains_runnable_entrypoint_files():
    entries = {path.name for path in (ROOT / "services" / "core").iterdir()}

    assert "README.md" in entries
    assert "__init__.py" in entries
    assert "main.py" in entries


def test_core_service_entrypoint_help_is_runnable():
    completed = subprocess.run(
        [sys.executable, "-m", "services.core.main", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "--health-once" in completed.stdout
    assert "--serve" in completed.stdout
    assert "127.0.0.1" in completed.stdout


def test_core_service_entrypoint_health_once_emits_contracts():
    completed = subprocess.run(
        [sys.executable, "-m", "services.core.main", "--health-once"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(completed.stdout)
    health = HealthCheck.model_validate(payload["health"])
    version = VersionInfo.model_validate(payload["version"])

    assert health.schema_version == SCHEMA_VERSION
    assert health.service == "marvex-core-service"
    assert health.status == HealthStatus.OK
    assert health.dependencies["turn_executor"]["configured"] is True
    assert version.service == "marvex-core-service"
    assert version.contract_versions["CoreService"] == SCHEMA_VERSION
    assert completed.stderr == ""


def test_core_service_entrypoint_starts_local_api_and_shuts_down_cleanly():
    from services.core.main import CoreServiceEntrypointConfig, run_core_service

    captured: dict[str, object] = {}

    class ExercisingServer:
        def __init__(self, app) -> None:
            self.app = app
            self.closed = False

        def serve_forever(self) -> None:
            health_status, health_payload = _call_app(self.app, "/health")
            turn_status, turn_payload = _call_app(
                self.app,
                "/v1/turns",
                method="POST",
                body=_turn_payload(),
                auth=f"Bearer {EXPECTED_TOKEN}",
            )
            invalid_status, invalid_payload = _call_app(
                self.app,
                "/v1/turns",
                method="POST",
                body={"schema_version": SCHEMA_VERSION},
                auth=f"Bearer {EXPECTED_TOKEN}",
            )
            captured["health"] = (health_status, health_payload)
            captured["turn"] = (turn_status, turn_payload)
            captured["invalid"] = (invalid_status, invalid_payload)
            raise KeyboardInterrupt

        def server_close(self) -> None:
            self.closed = True
            captured["closed"] = True

    def server_factory(host, port, app):
        captured["host"] = host
        captured["port"] = port
        captured["app"] = app
        server = ExercisingServer(app)
        captured["server"] = server
        return server

    exit_code = run_core_service(
        config=CoreServiceEntrypointConfig(
            local_auth_token=EXPECTED_TOKEN,
            port=9877,
        ),
        server_factory=server_factory,
    )

    assert exit_code == 0
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 9877
    assert captured["closed"] is True

    health_status, health_payload = captured["health"]
    health = HealthCheck.model_validate(health_payload)
    assert health_status == "200 OK"
    assert health.service == "marvex-core-service"
    assert health.status == HealthStatus.OK

    turn_status, turn_payload = captured["turn"]
    result = AssistantTurnResult.model_validate(turn_payload)
    assert turn_status == "200 OK"
    assert result.trace_id == "trace-core-entrypoint"
    assert result.turn_id == "turn-core-entrypoint"
    assert result.error is None

    invalid_status, invalid_payload = captured["invalid"]
    error = ErrorEnvelope.model_validate(invalid_payload)
    assert invalid_status == "400 Bad Request"
    assert error.code == ErrorCode.VALIDATION_ERROR
    assert error.source == "local_api"


def test_core_service_entrypoint_starts_control_plane_state_api():
    from services.core.main import CoreServiceEntrypointConfig, run_core_service

    captured: dict[str, object] = {}

    class MainServer:
        def serve_forever(self) -> None:
            raise KeyboardInterrupt

        def server_close(self) -> None:
            captured["main_closed"] = True

    class ControlServer:
        def __init__(self, app) -> None:
            self.app = app

        def serve_forever(self) -> None:
            state_status, state_payload = _call_app(
                self.app,
                "/control/state",
                auth=f"Bearer {EXPECTED_TOKEN}",
            )
            stream_status, stream_payload = _call_first_stream_frame(
                self.app,
                "/control/state/stream",
                auth=f"Bearer {EXPECTED_TOKEN}",
            )
            captured["control_state"] = (state_status, state_payload)
            captured["control_stream"] = (stream_status, stream_payload)

        def server_close(self) -> None:
            captured["control_closed"] = True

    def main_server_factory(host, port, app):
        captured["main_host"] = host
        captured["main_port"] = port
        return MainServer()

    def control_server_factory(host, port, app):
        captured["control_host"] = host
        captured["control_port"] = port
        return ControlServer(app)

    exit_code = run_core_service(
        config=CoreServiceEntrypointConfig(
            local_auth_token=EXPECTED_TOKEN,
            port=9877,
            control_port=9878,
        ),
        server_factory=main_server_factory,
        control_server_factory=control_server_factory,
    )

    assert exit_code == 0
    assert captured["control_host"] == "127.0.0.1"
    assert captured["control_port"] == 9878
    assert captured["control_closed"] is True

    state_status, state_payload = captured["control_state"]
    assert state_status == "200 OK"
    assert state_payload["status"] == "idle"
    assert state_payload["raw_audio_persisted"] is False

    stream_status, stream_payload = captured["control_stream"]
    assert stream_status == "200 OK"
    assert stream_payload["status"] == "idle"
    assert stream_payload["raw_audio_persisted"] is False


def _call_first_stream_frame(app, path: str, *, auth: str) -> tuple[str, dict]:
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = "GET"
    environ["PATH_INFO"] = path
    environ["HTTP_AUTHORIZATION"] = auth
    environ["CONTENT_LENGTH"] = "0"
    environ["wsgi.input"] = BytesIO(b"")
    captured: dict[str, object] = {}

    def start_response(status, _headers, exc_info=None):
        captured["status"] = status

    frame = next(iter(app(environ, start_response))).decode("utf-8")
    payload = json.loads(frame.removeprefix("data: ").strip())
    return str(captured["status"]), payload


def test_core_service_entrypoint_rejects_remote_bind_configuration():
    from services.core.main import CoreServiceEntrypointConfig, run_core_service

    try:
        run_core_service(
            config=CoreServiceEntrypointConfig(
                host="0.0.0.0",
                local_auth_token=EXPECTED_TOKEN,
            ),
            server_factory=lambda *_args: None,
        )
    except ValueError as exc:
        assert str(exc) == "host must be loopback-only"
    else:
        raise AssertionError("Core service entrypoint must reject remote binds")


def test_core_service_entrypoint_allows_remote_bind_when_opted_in():
    from services.core.main import CoreServiceEntrypointConfig, run_core_service

    captured: dict[str, object] = {}

    class _StubServer:
        def __init__(self, app) -> None:
            self.app = app

        def serve_forever(self) -> None:
            raise KeyboardInterrupt

        def server_close(self) -> None:
            captured["closed"] = True

    def server_factory(host, port, app):
        captured["host"] = host
        return _StubServer(app)

    exit_code = run_core_service(
        config=CoreServiceEntrypointConfig(
            host="192.0.2.10",
            local_auth_token=EXPECTED_TOKEN,
            allow_remote=True,
        ),
        server_factory=server_factory,
    )

    assert exit_code == 0
    assert captured["host"] == "192.0.2.10"
    assert captured["closed"] is True


def test_core_service_entrypoint_remote_bind_still_requires_auth_token():
    from services.core.main import CoreServiceEntrypointConfig, run_core_service

    try:
        run_core_service(
            config=CoreServiceEntrypointConfig(
                host="192.0.2.10",
                allow_remote=True,
            ),
            server_factory=lambda *_args: None,
        )
    except ValueError as exc:
        assert "local_auth_token is required" in str(exc)
    else:
        raise AssertionError("remote bind must require an auth token")


def test_core_service_entrypoint_boundary_gate_passes():
    completed = subprocess.run(
        [sys.executable, "scripts/check_service_placeholders.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS service placeholder policy" in completed.stdout


def test_local_api_boundary_gate_allows_approved_core_service_entrypoint():
    completed = subprocess.run(
        [sys.executable, "scripts/check_local_api_boundaries.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS local API boundaries" in completed.stdout
