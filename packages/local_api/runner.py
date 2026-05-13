from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any
from wsgiref.simple_server import make_server

from packages.process_runtime import HealthVersionProvider, ProcessRuntimeConfig

from .health_version_api import LocalApiConfig, WsgiApp, create_health_version_api_app


SERVICE_NAME = "marvex-local-api"
SERVICE_VERSION = "0.1.0"
SCHEMA_VERSION = "0.1.1-draft"
CONTRACT_VERSIONS = {
    "HealthCheck": SCHEMA_VERSION,
    "VersionInfo": SCHEMA_VERSION,
}

Clock = Callable[[], datetime]
ServerFactory = Callable[[str, int, WsgiApp], Any]


def create_default_health_version_provider(
    *,
    started_at: datetime | None = None,
    clock: Clock | None = None,
) -> HealthVersionProvider:
    effective_started_at = started_at or datetime.now(UTC)
    effective_clock = clock or (lambda: datetime.now(UTC))
    return HealthVersionProvider(
        ProcessRuntimeConfig(
            service_name=SERVICE_NAME,
            service_version=SERVICE_VERSION,
            schema_version=SCHEMA_VERSION,
            started_at=effective_started_at,
            clock=effective_clock,
            contract_versions=CONTRACT_VERSIONS,
            build={"version": SERVICE_VERSION},
            dependencies={},
        )
    )


def run_local_health_version_api(
    *,
    config: LocalApiConfig = LocalApiConfig(),
    provider: HealthVersionProvider | None = None,
    server_factory: ServerFactory = make_server,
) -> int:
    effective_provider = provider or create_default_health_version_provider()
    app = create_health_version_api_app(effective_provider)
    httpd = server_factory(config.host, config.port, app)
    print(f"Local health/version API listening on http://{config.host}:{config.port}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("Local health/version API stopped.")
    finally:
        httpd.server_close()
    return 0


def main() -> int:
    return run_local_health_version_api()


if __name__ == "__main__":
    raise SystemExit(main())
