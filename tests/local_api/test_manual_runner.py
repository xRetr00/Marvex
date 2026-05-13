from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from wsgiref.util import setup_testing_defaults

from packages.contracts import ErrorEnvelope, HealthCheck, VersionInfo
from packages.process_runtime import HealthVersionProvider, ProcessRuntimeConfig


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
