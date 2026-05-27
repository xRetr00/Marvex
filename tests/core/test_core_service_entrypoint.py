from __future__ import annotations

# file size justification: Core service entrypoint tests intentionally keep CLI, auth, ASGI host, session wiring, and smoke regressions together until service startup contracts are split by owned boundary.

import json
import subprocess
import sys
from pathlib import Path

from fastapi.testclient import TestClient

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
    headers: dict[str, str] = {}
    if auth is not None:
        headers["Authorization"] = auth
    response = TestClient(app).request(method, path, headers=headers, json=body, follow_redirects=False)
    return f"{response.status_code} {response.reason_phrase}", response.json()


def _turn_payload(
    *,
    trace_id: str = "trace-core-entrypoint",
    turn_id: str = "turn-core-entrypoint",
    session_id: str | None = None,
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "execution_mode": "assistant_runtime_fake_provider",
        "assistant_turn_input": {
            "schema_version": SCHEMA_VERSION,
            "trace_id": trace_id,
            "turn_id": turn_id,
            "input_event_id": "event-core-entrypoint",
            "session_ref": (
                {"ref_type": "session", "ref_id": session_id}
                if session_id is not None
                else None
            ),
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

    def control_server_factory(host, port, app):
        captured["control_host"] = host
        captured["control_port"] = port
        return MainNoopServer()

    class MainNoopServer:
        def serve_forever(self) -> None:
            return

        def server_close(self) -> None:
            captured["control_closed"] = True

    exit_code = run_core_service(
        config=CoreServiceEntrypointConfig(
            local_auth_token=EXPECTED_TOKEN,
            port=9877,
        ),
        server_factory=server_factory,
        control_server_factory=control_server_factory,
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
            stream_status, stream_payload = _call_app(
                self.app,
                "/control/state",
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


def test_core_service_entrypoint_default_serve_uses_asgi_host(monkeypatch):
    import services.core.main as core_main
    from services.core.main import CoreServiceEntrypointConfig, run_core_service

    captured: dict[str, object] = {}

    def fake_run_dual_asgi_host(**kwargs):
        captured.update(kwargs)
        return 0

    monkeypatch.setattr(core_main, "run_dual_asgi_host", fake_run_dual_asgi_host)

    exit_code = run_core_service(
        config=CoreServiceEntrypointConfig(
            local_auth_token=EXPECTED_TOKEN,
            port=9877,
            control_port=9878,
        ),
    )

    assert exit_code == 0
    assert captured["core_app"].title == "Marvex Core API"
    assert captured["control_app"].title == "Marvex Control Plane"
    assert captured["startup_message"].startswith("Core service startup metadata: ")
    asgi_config = captured["config"]
    assert asgi_config.host == "127.0.0.1"
    assert asgi_config.port == 9877
    assert asgi_config.control_host == "127.0.0.1"
    assert asgi_config.control_port == 9878


def test_core_service_entrypoint_shares_backend_session_truth_with_control_plane(monkeypatch):
    import services.core.main as core_main
    from services.core.main import CoreServiceEntrypointConfig, run_core_service

    captured: dict[str, object] = {}

    def fake_run_dual_asgi_host(**kwargs):
        from fastapi.testclient import TestClient

        captured.update(kwargs)
        control_app = kwargs["control_app"]
        core_app = kwargs["core_app"]
        auth = f"Bearer {EXPECTED_TOKEN}"
        create_status, create_payload = _call_app(control_app, "/control/sessions", method="POST", body={"title": "Shared session"}, auth=auth)
        session_id = create_payload["session"]["session_ref"]["ref_id"]
        turn_status, turn_payload = _call_app(core_app, "/v1/turns", method="POST", body=_turn_payload(session_id=session_id), auth=auth)
        list_status, list_payload = _call_app(control_app, "/control/sessions", auth=auth)
        asgi_response = TestClient(kwargs["control_app"]).get("/control/sessions", headers={"Authorization": auth})
        captured["session_result"] = {
            "create_status": create_status,
            "session_id": session_id,
            "turn_status": turn_status,
            "turn_payload": turn_payload,
            "list_status": list_status,
            "list_payload": list_payload,
            "asgi_status": asgi_response.status_code,
            "asgi_payload": asgi_response.json(),
        }
        return 0

    monkeypatch.setattr(core_main, "run_dual_asgi_host", fake_run_dual_asgi_host)

    exit_code = run_core_service(
        config=CoreServiceEntrypointConfig(
            local_auth_token=EXPECTED_TOKEN,
            port=9877,
            control_port=9878,
        ),
    )

    assert exit_code == 0
    result = captured["session_result"]
    assert result["create_status"] == "200 OK"
    assert result["turn_status"] == "200 OK"
    assert result["turn_payload"]["metadata"]["session"]["turn_count"] == 1

    session_id = result["session_id"]
    list_payload = result["list_payload"]
    assert result["list_status"] == "200 OK"
    assert list_payload["sessions"][0]["session_ref"]["ref_id"] == session_id
    assert list_payload["sessions"][0]["turn_count"] == 1
    assert list_payload["sessions"][0]["transcript_persisted"] is False
    assert result["asgi_status"] == 200
    assert result["asgi_payload"]["sessions"][0]["session_ref"]["ref_id"] == session_id
    assert result["asgi_payload"]["sessions"][0]["turn_count"] == 1


def test_core_service_entrypoint_shares_pending_approvals_with_control_plane(monkeypatch):
    import services.core.main as core_main
    from services.core.main import CoreServiceEntrypointConfig, run_core_service

    captured: dict[str, object] = {}

    def fake_run_dual_asgi_host(**kwargs):
        auth = f"Bearer {EXPECTED_TOKEN}"
        core_payload = _turn_payload()
        core_payload["assistant_turn_input"]["user_visible_input"] = "open browser page"
        turn_status, turn_payload = _call_app(kwargs["core_app"], "/v1/turns", method="POST", body=core_payload, auth=auth)
        approvals_status, approvals_payload = _call_app(kwargs["control_app"], "/control/approvals", auth=auth)
        captured["result"] = {
            "turn_status": turn_status,
            "turn_payload": turn_payload,
            "approvals_status": approvals_status,
            "approvals_payload": approvals_payload,
        }
        return 0

    monkeypatch.setattr(core_main, "run_dual_asgi_host", fake_run_dual_asgi_host)

    exit_code = run_core_service(
        config=CoreServiceEntrypointConfig(
            local_auth_token=EXPECTED_TOKEN,
            port=9877,
            control_port=9878,
        ),
    )

    assert exit_code == 0
    result = captured["result"]
    assert result["turn_status"] == "200 OK"
    assert result["turn_payload"]["metadata"]["agentic_loop"]["stop_reason"] == "waiting_for_human_approval"
    assert result["approvals_status"] == "200 OK"
    assert result["approvals_payload"]["pending_count"] == 1
    assert result["approvals_payload"]["approvals"][0]["approval_request_id"].startswith("approval-turn-core-entrypoint")


def test_core_service_entrypoint_main_uses_env_token_for_supervisor_path(monkeypatch):
    import services.core.main as core_main

    captured: dict[str, object] = {}

    def fake_run_core_service(*, config):
        captured["config"] = config
        return 0

    monkeypatch.setenv("MARVEX_LOCAL_AUTH_TOKEN", "env-token-for-supervisor")
    monkeypatch.setattr(core_main, "run_core_service", fake_run_core_service)

    exit_code = core_main.main(["--serve"])

    assert exit_code == 0
    assert captured["config"].local_auth_token == "env-token-for-supervisor"


def test_core_service_entrypoint_cli_token_overrides_env_token(monkeypatch):
    import services.core.main as core_main

    captured: dict[str, object] = {}

    def fake_run_core_service(*, config):
        captured["config"] = config
        return 0

    monkeypatch.setenv("MARVEX_LOCAL_AUTH_TOKEN", "env-token")
    monkeypatch.setattr(core_main, "run_core_service", fake_run_core_service)

    exit_code = core_main.main(["--serve", "--local-auth-token", "cli-token"])

    assert exit_code == 0
    assert captured["config"].local_auth_token == "cli-token"


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

    def control_server_factory(host, port, app):
        return _ControlNoopServer()

    class _ControlNoopServer:
        def serve_forever(self) -> None:
            return

        def server_close(self) -> None:
            captured["control_closed"] = True

    exit_code = run_core_service(
        config=CoreServiceEntrypointConfig(
            host="192.0.2.10",
            local_auth_token=EXPECTED_TOKEN,
            allow_remote=True,
        ),
        server_factory=server_factory,
        control_server_factory=control_server_factory,
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


def test_core_control_plane_app_explicitly_composes_voice_worker_facade(monkeypatch):
    from services.core import main
    from services.core.main import CoreServiceEntrypointConfig
    import packages.voice_worker_runtime as voice_worker_runtime

    captured: dict[str, object] = {}
    facade = object()

    monkeypatch.setattr(voice_worker_runtime, "VoiceWorkerControlPlaneFacade", lambda: facade)
    monkeypatch.setattr(main, "ControlPlaneRuntime", lambda **kwargs: captured.update(kwargs) or kwargs)

    main.create_control_plane_service_app(config=CoreServiceEntrypointConfig(local_auth_token=EXPECTED_TOKEN))

    assert captured["voice_worker_control"] is facade


def test_local_api_boundary_gate_allows_approved_core_service_entrypoint():
    completed = subprocess.run(
        [sys.executable, "scripts/check_local_api_boundaries.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "PASS local API boundaries" in completed.stdout


def test_composite_trace_reader_lists_in_memory_and_persistent_trace_ids(tmp_path):
    from datetime import UTC, datetime

    from packages.contracts import TraceLevel, TraceStage
    from packages.telemetry import InMemoryTraceReader, PersistentTraceStore, make_trace_event
    from services.core.main import _CompositeTraceReader

    in_memory = InMemoryTraceReader()
    persistent = PersistentTraceStore(
        trace_file_path=tmp_path / "telemetry" / "traces.jsonl",
        local_user_root=tmp_path,
    )
    event = make_trace_event(
        schema_version=SCHEMA_VERSION,
        trace_id="trace-in-memory",
        turn_id="turn-in-memory",
        stage=TraceStage.TURN_COMPLETED,
        level=TraceLevel.INFO,
        message="Turn completed.",
        data={"status": "completed"},
        timestamp=datetime(2026, 5, 18, tzinfo=UTC),
    )
    in_memory.emit(event)
    persistent.emit(event.model_copy(update={"trace_id": "trace-persisted"}))
    reader = _CompositeTraceReader(in_memory=in_memory, persistent=persistent)

    assert reader.trace_ids(limit=10) == ("trace-persisted", "trace-in-memory")


def test_persist_trace_events_does_not_duplicate_existing_event_ids(tmp_path):
    from datetime import UTC, datetime

    from packages.contracts import TraceLevel, TraceStage
    from packages.telemetry import InMemoryTraceReader, PersistentTraceStore, make_trace_event
    from services.core.main import _persist_trace_events

    reader = InMemoryTraceReader()
    store = PersistentTraceStore(
        trace_file_path=tmp_path / "telemetry" / "traces.jsonl",
        local_user_root=tmp_path,
    )
    reader.emit(
        make_trace_event(
            schema_version=SCHEMA_VERSION,
            trace_id="trace-persist-once",
            turn_id="turn-persist-once",
            stage=TraceStage.TURN_RECEIVED,
            level=TraceLevel.INFO,
            message="Turn received.",
            data={"status": "received"},
            timestamp=datetime(2026, 5, 18, tzinfo=UTC),
        )
    )

    _persist_trace_events(store, reader, "trace-persist-once")
    _persist_trace_events(store, reader, "trace-persist-once")

    envelope = store.read_trace("trace-persist-once")
    assert envelope["event_count"] == 1


def test_core_service_turn_writes_safe_operational_logs_when_log_dir_is_configured(tmp_path, monkeypatch):
    from packages.contracts import AssistantTurnInput
    from services.core.main import CoreServiceEntrypointConfig, create_core_service

    monkeypatch.setenv("MARVEX_LOG_DIR", str(tmp_path))
    service = create_core_service(
        config=CoreServiceEntrypointConfig(local_auth_token=EXPECTED_TOKEN, provider="fake")
    )
    service.start()

    result = service.submit_turn(
        AssistantTurnInput.model_validate(_turn_payload()["assistant_turn_input"]),
        previous_response_id="resp-previous-log",
    )

    assert result.error is None
    turns_log = tmp_path / "turns.log"
    behavior_log = tmp_path / "behavior.log"
    telemetry_log = tmp_path / "telemetry.log"
    provider_log = tmp_path / "provider.log"
    continuation_log = tmp_path / "continuation.log"
    traces_jsonl = tmp_path / "traces.jsonl"
    assert turns_log.exists()
    assert behavior_log.exists()
    assert telemetry_log.exists()
    assert provider_log.exists()
    assert continuation_log.exists()
    assert traces_jsonl.exists()
    turns_text = turns_log.read_text(encoding="utf-8")
    assert "trace=trace-core-entrypoint" in turns_text
    assert "turn=turn-core-entrypoint" in turns_text
    assert "stage=" in turns_text
    assert "secret" not in turns_text.lower()
    provider_text = provider_log.read_text(encoding="utf-8")
    assert "stage=provider_request_sent" in provider_text
    assert "previous_response_id_present=True" in provider_text
    continuation_text = continuation_log.read_text(encoding="utf-8")
    assert "previous_response_id_present=True" in continuation_text
    assert "trace-core-entrypoint" in traces_jsonl.read_text(encoding="utf-8")


def test_core_service_defaults_trace_persistence_to_log_dir(tmp_path, monkeypatch):
    from services.core.main import CoreServiceEntrypointConfig, _persistent_store_from_config

    monkeypatch.setenv("MARVEX_LOG_DIR", str(tmp_path))

    store = _persistent_store_from_config(CoreServiceEntrypointConfig())

    assert store is not None
    assert store._trace_file_path == tmp_path / "traces.jsonl"


def test_core_service_file_capability_root_can_come_from_environment(tmp_path, monkeypatch):
    from services.core.main import CoreServiceEntrypointConfig, _effective_file_capability_root

    monkeypatch.setenv("MARVEX_FILE_CAPABILITY_ROOT", str(tmp_path))

    assert _effective_file_capability_root(CoreServiceEntrypointConfig()) == str(tmp_path)
    assert _effective_file_capability_root(CoreServiceEntrypointConfig(file_capability_root="explicit")) == "explicit"
