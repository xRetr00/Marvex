from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from wsgiref.util import setup_testing_defaults

from packages.contracts import ErrorCode, ErrorEnvelope, HealthCheck, VersionInfo
from packages.process_runtime import HealthVersionProvider, ProcessRuntimeConfig


def make_provider() -> HealthVersionProvider:
    started_at = datetime(2026, 5, 13, 12, 0, tzinfo=UTC)
    return HealthVersionProvider(
        ProcessRuntimeConfig(
            service_name="marvex-local-api",
            service_version="0.1.0",
            started_at=started_at,
            clock=lambda: started_at + timedelta(seconds=7),
            contract_versions={
                "HealthCheck": "0.1.1-draft",
                "VersionInfo": "0.1.1-draft",
            },
            build={"version": "0.1.0"},
            dependencies={},
        )
    )


def call_app(app, path: str, *, method: str = "GET") -> tuple[str, dict[str, str], dict]:
    environ: dict[str, object] = {}
    setup_testing_defaults(environ)
    environ["REQUEST_METHOD"] = method
    environ["PATH_INFO"] = path
    captured: dict[str, object] = {}

    def start_response(status, headers, exc_info=None):
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = b"".join(app(environ, start_response)).decode("utf-8")
    return captured["status"], captured["headers"], json.loads(body)


def test_health_returns_valid_health_check_json():
    from packages.local_api import create_health_version_api_app

    app = create_health_version_api_app(make_provider())

    status, headers, payload = call_app(app, "/health")

    health = HealthCheck.model_validate(payload)
    assert status == "200 OK"
    assert headers["Content-Type"] == "application/json"
    assert health.schema_version == "0.1.1-draft"
    assert health.service == "marvex-local-api"
    assert health.status == "ok"
    assert health.version == "0.1.0"
    assert health.uptime_seconds == 7
    assert health.dependencies == {}


def test_version_returns_valid_version_info_json():
    from packages.local_api import create_health_version_api_app

    app = create_health_version_api_app(make_provider())

    status, headers, payload = call_app(app, "/version")

    version = VersionInfo.model_validate(payload)
    assert status == "200 OK"
    assert headers["Content-Type"] == "application/json"
    assert version.schema_version == "0.1.1-draft"
    assert version.service == "marvex-local-api"
    assert version.service_version == "0.1.0"
    assert version.contract_versions == {
        "HealthCheck": "0.1.1-draft",
        "VersionInfo": "0.1.1-draft",
    }
    assert version.build == {"version": "0.1.0"}


def test_unknown_route_returns_deterministic_error_envelope():
    from packages.local_api import create_health_version_api_app

    app = create_health_version_api_app(make_provider())

    status, headers, payload = call_app(app, "/v1/turns")

    error = ErrorEnvelope.model_validate(payload)
    assert status == "404 Not Found"
    assert headers["Content-Type"] == "application/json"
    assert error.code == ErrorCode.NOT_FOUND
    assert error.message == "Endpoint not found."
    assert error.source == "local_api"
    assert error.details == {"path": "/v1/turns"}


def test_local_api_config_defaults_to_loopback_only():
    from packages.local_api import LocalApiConfig

    config = LocalApiConfig()

    assert config.host == "127.0.0.1"
    assert config.port == 8765


def test_local_api_source_has_no_provider_or_assistant_execution():
    source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted((Path("packages") / "local_api").rglob("*.py"))
    )
    forbidden = [
        "packages.provider_runtime",
        "packages.runtime_composition",
        "packages.core",
        "packages.assistant_runtime",
        "packages.adapters",
        "run_lmstudio_responses_assistant_bridge",
        "run_fake_provider_assistant_bridge",
        "run_assistant_provider_stage_turn",
        "run_provider_stage_turn",
        "TurnOrchestrator",
        "ProviderRuntimeConfig",
        "create_provider",
        "ProviderRequest",
        "ProviderResponse",
        "session",
        "history",
        "retry",
        "fallback",
        "model selection",
        "api_key",
        "websocket",
    ]

    assert [token for token in forbidden if token in source] == []
