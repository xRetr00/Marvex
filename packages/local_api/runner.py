from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from packages.process_runtime import HealthVersionProvider, ProcessRuntimeConfig

from .asgi_app import create_local_api_asgi_app
from .asgi_host import run_asgi_host
from .contracts import (
    LocalApiConfig,
    TraceReader,
    TurnHandler,
)


SERVICE_NAME = "marvex-local-api"
SERVICE_VERSION = "0.2.0"
SCHEMA_VERSION = "0.1.1-draft"
CONTRACT_VERSIONS = {
    "HealthCheck": SCHEMA_VERSION,
    "VersionInfo": SCHEMA_VERSION,
}

Clock = Callable[[], datetime]
ServerFactory = Callable[..., Any]


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
    server_factory: ServerFactory | None = None,
    turn_handler: TurnHandler | None = None,
    trace_reader: TraceReader | None = None,
    local_auth_token: str | None = None,
    accepted_turn_execution_modes: tuple[str, ...] | None = None,
    startup_message: str | None = None,
) -> int:
    effective_provider = provider or create_default_health_version_provider()
    app_kwargs = {
        "turn_handler": turn_handler,
        "trace_reader": trace_reader,
        "local_auth_token": local_auth_token,
    }
    if accepted_turn_execution_modes is not None:
        app_kwargs["accepted_turn_execution_modes"] = accepted_turn_execution_modes
    app = create_local_api_asgi_app(
        effective_provider,
        **app_kwargs,
    )
    return run_asgi_host(
        app=app,
        host=config.host,
        port=config.port,
        server_factory=server_factory,
        startup_message=startup_message
        or f"Local health/version API listening on http://{config.host}:{config.port}",
    )


def main() -> int:
    return run_local_health_version_api()


if __name__ == "__main__":
    raise SystemExit(main())
