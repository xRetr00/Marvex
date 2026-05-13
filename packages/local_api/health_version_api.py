from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from packages.contracts import ErrorCode, ErrorEnvelope
from packages.process_runtime import HealthVersionProvider


StartResponse = Callable[
    [str, list[tuple[str, str]], object | None],
    object,
]
WsgiApp = Callable[[dict[str, Any], StartResponse], Iterable[bytes]]


@dataclass(frozen=True)
class LocalApiConfig:
    host: str = "127.0.0.1"
    port: int = 8765


def create_health_version_api_app(
    provider: HealthVersionProvider,
) -> WsgiApp:
    def app(environ: dict[str, Any], start_response: StartResponse) -> Iterable[bytes]:
        method = str(environ.get("REQUEST_METHOD", "GET")).upper()
        path = str(environ.get("PATH_INFO", "/"))
        if method == "GET" and path == "/health":
            return _json_response(
                start_response,
                "200 OK",
                provider.get_health().model_dump_json(),
            )
        if method == "GET" and path == "/version":
            return _json_response(
                start_response,
                "200 OK",
                provider.get_version().model_dump_json(),
            )
        return _json_response(
            start_response,
            "404 Not Found",
            ErrorEnvelope(
                schema_version="0.1.1-draft",
                trace_id="trace-local-api-not-found",
                error_id="local-api-not-found",
                code=ErrorCode.NOT_FOUND,
                message="Endpoint not found.",
                recoverable=False,
                source="local_api",
                details={"path": path},
            ).model_dump_json(),
        )

    return app


def _json_response(
    start_response: StartResponse,
    status: str,
    body: str,
) -> list[bytes]:
    encoded = body.encode("utf-8")
    start_response(
        status,
        [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(encoded))),
        ],
        None,
    )
    return [encoded]
