from __future__ import annotations

import json
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, Protocol

from packages.contracts import (
    AssistantTurnInput,
    AssistantTurnResult,
    ErrorCode,
    ErrorEnvelope,
)
from packages.process_runtime import HealthVersionProvider

from .auth_policy import validate_local_bearer_token


StartResponse = Callable[
    [str, list[tuple[str, str]], object | None],
    object,
]
WsgiApp = Callable[[dict[str, Any], StartResponse], Iterable[bytes]]
SCHEMA_VERSION = "0.1.1-draft"
LOCAL_TURNS_PATH = "/v1/turns"
LOCAL_TRACES_PREFIX = "/v1/traces/"
LOCAL_TURNS_EXECUTION_MODE = "assistant_runtime_fake_provider"
LOCAL_TURN_REQUEST_FIELDS = {
    "schema_version",
    "execution_mode",
    "assistant_turn_input",
    "model",
    "instructions",
    "previous_response_id",
    "provider_options",
}


@dataclass(frozen=True)
class LocalApiConfig:
    host: str = "127.0.0.1"
    port: int = 8765


@dataclass(frozen=True)
class LocalTurnRequestEnvelope:
    schema_version: str
    execution_mode: str
    assistant_turn_input: AssistantTurnInput
    model: str
    instructions: str | None
    previous_response_id: str | None
    provider_options: dict[str, Any]


TurnHandler = Callable[[LocalTurnRequestEnvelope], AssistantTurnResult]


class TraceReader(Protocol):
    def read_trace(self, trace_id: str) -> dict[str, Any] | None:
        ...


def create_health_version_api_app(
    provider: HealthVersionProvider,
    *,
    turn_handler: TurnHandler | None = None,
    trace_reader: TraceReader | None = None,
    local_auth_token: str | None = None,
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
        if method == "POST" and path == LOCAL_TURNS_PATH:
            return _handle_turn_request(
                environ,
                start_response,
                turn_handler=turn_handler,
                expected_auth_value=local_auth_token or "",
            )
        if method == "GET" and path.startswith(LOCAL_TRACES_PREFIX):
            return _handle_trace_request(
                environ,
                start_response,
                path=path,
                trace_reader=trace_reader,
                expected_auth_value=local_auth_token or "",
            )
        return _json_response(
            start_response,
            "404 Not Found",
            ErrorEnvelope(
                schema_version=SCHEMA_VERSION,
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


def _handle_trace_request(
    environ: dict[str, Any],
    start_response: StartResponse,
    *,
    path: str,
    trace_reader: TraceReader | None,
    expected_auth_value: str,
) -> Iterable[bytes]:
    auth_error = validate_local_bearer_token(
        authorization_header=_authorization_header(environ),
        expected_token=expected_auth_value,
        trace_id="trace-local-api-auth-required",
    )
    if auth_error is not None:
        return _json_response(
            start_response,
            "401 Unauthorized",
            auth_error.model_dump_json(),
        )

    trace_id = path[len(LOCAL_TRACES_PREFIX) :]
    if not _valid_trace_id(trace_id):
        return _json_response(
            start_response,
            "400 Bad Request",
            _error_envelope(
                trace_id="trace-local-api-validation-error",
                error_id="local-api-trace-validation-error",
                code=ErrorCode.VALIDATION_ERROR,
                message="Local API trace request validation failed.",
                recoverable=False,
                reason="invalid_trace_id",
            ).model_dump_json(),
        )

    if trace_reader is None:
        return _json_response(
            start_response,
            "503 Service Unavailable",
            _error_envelope(
                trace_id=trace_id,
                error_id="local-api-trace-reader-unavailable",
                code=ErrorCode.SERVICE_UNHEALTHY,
                message="Local API trace reader unavailable.",
                recoverable=True,
                reason="trace_reader_unavailable",
            ).model_dump_json(),
        )

    try:
        envelope = trace_reader.read_trace(trace_id)
    except Exception:
        return _json_response(
            start_response,
            "500 Internal Server Error",
            _error_envelope(
                trace_id=trace_id,
                error_id="local-api-trace-reader-failed",
                code=ErrorCode.INTERNAL_ERROR,
                message="Local API trace reader failed.",
                recoverable=False,
                reason="trace_reader_failure",
            ).model_dump_json(),
        )

    if envelope is None:
        return _json_response(
            start_response,
            "404 Not Found",
            _error_envelope(
                trace_id=trace_id,
                error_id="local-api-trace-not-found",
                code=ErrorCode.NOT_FOUND,
                message="Local API trace not found.",
                recoverable=False,
                reason="trace_not_found",
            ).model_dump_json(),
        )

    try:
        response_body = json.dumps(envelope)
    except Exception:
        return _json_response(
            start_response,
            "500 Internal Server Error",
            _error_envelope(
                trace_id=trace_id,
                error_id="local-api-trace-reader-failed",
                code=ErrorCode.INTERNAL_ERROR,
                message="Local API trace reader failed.",
                recoverable=False,
                reason="trace_reader_failure",
            ).model_dump_json(),
        )

    return _json_response(start_response, "200 OK", response_body)


def _handle_turn_request(
    environ: dict[str, Any],
    start_response: StartResponse,
    *,
    turn_handler: TurnHandler | None,
    expected_auth_value: str,
) -> Iterable[bytes]:
    auth_error = validate_local_bearer_token(
        authorization_header=_authorization_header(environ),
        expected_token=expected_auth_value,
        trace_id="trace-local-api-auth-required",
    )
    if auth_error is not None:
        return _json_response(
            start_response,
            "401 Unauthorized",
            auth_error.model_dump_json(),
        )

    if turn_handler is None:
        return _json_response(
            start_response,
            "503 Service Unavailable",
            _error_envelope(
                trace_id="trace-local-api-turn-handler-unavailable",
                error_id="local-api-turn-handler-unavailable",
                code=ErrorCode.SERVICE_UNHEALTHY,
                message="Local API turn handler unavailable.",
                recoverable=True,
                reason="handler_unavailable",
            ).model_dump_json(),
        )

    request = _parse_turn_request(environ)
    if isinstance(request, ErrorEnvelope):
        return _json_response(start_response, "400 Bad Request", request.model_dump_json())

    try:
        result = turn_handler(request)
    except Exception:
        return _json_response(
            start_response,
            "500 Internal Server Error",
            _error_envelope(
                trace_id=request.assistant_turn_input.trace_id,
                error_id="local-api-turn-handler-failed",
                code=ErrorCode.INTERNAL_ERROR,
                message="Local API turn handler failed.",
                recoverable=False,
                reason="handler_failure",
            ).model_dump_json(),
        )

    return _json_response(start_response, "200 OK", result.model_dump_json())


def _authorization_header(environ: dict[str, Any]) -> str | None:
    value = environ.get("HTTP_AUTHORIZATION")
    return value if isinstance(value, str) else None


def _valid_trace_id(trace_id: str) -> bool:
    if not trace_id.strip():
        return False
    return all(character.isalnum() or character in ".:-_" for character in trace_id)


def _parse_turn_request(
    environ: dict[str, Any],
) -> LocalTurnRequestEnvelope | ErrorEnvelope:
    try:
        raw_body = _read_request_body(environ)
        payload = json.loads(raw_body)
    except Exception:
        return _validation_error("invalid_json")

    if not isinstance(payload, dict):
        return _validation_error("request_must_be_object")

    if set(payload) != LOCAL_TURN_REQUEST_FIELDS:
        return _validation_error("invalid_request_fields")

    if payload["schema_version"] != SCHEMA_VERSION:
        return _validation_error("invalid_schema_version")
    if payload["execution_mode"] != LOCAL_TURNS_EXECUTION_MODE:
        return _validation_error("unsupported_execution_mode")
    if not isinstance(payload["model"], str) or not payload["model"].strip():
        return _validation_error("invalid_model")
    if payload["instructions"] is not None and not isinstance(payload["instructions"], str):
        return _validation_error("invalid_instructions")
    if (
        payload["previous_response_id"] is not None
        and (
            not isinstance(payload["previous_response_id"], str)
            or not payload["previous_response_id"].strip()
        )
    ):
        return _validation_error("invalid_previous_response_id")
    if not isinstance(payload["provider_options"], dict) or payload["provider_options"]:
        return _validation_error("invalid_provider_options")

    try:
        turn_input = AssistantTurnInput.model_validate(payload["assistant_turn_input"])
    except Exception:
        return _validation_error("invalid_assistant_turn_input")

    return LocalTurnRequestEnvelope(
        schema_version=payload["schema_version"],
        execution_mode=payload["execution_mode"],
        assistant_turn_input=turn_input,
        model=payload["model"],
        instructions=payload["instructions"],
        previous_response_id=payload["previous_response_id"],
        provider_options=payload["provider_options"],
    )


def _read_request_body(environ: dict[str, Any]) -> str:
    length_text = str(environ.get("CONTENT_LENGTH") or "0")
    content_length = int(length_text) if length_text.strip() else 0
    stream = environ["wsgi.input"]
    raw_body = stream.read(content_length)
    if isinstance(raw_body, bytes):
        return raw_body.decode("utf-8")
    return str(raw_body)


def _validation_error(reason: str) -> ErrorEnvelope:
    return _error_envelope(
        trace_id="trace-local-api-validation-error",
        error_id="local-api-validation-error",
        code=ErrorCode.VALIDATION_ERROR,
        message="Local API request validation failed.",
        recoverable=False,
        reason=reason,
    )


def _error_envelope(
    *,
    trace_id: str,
    error_id: str,
    code: ErrorCode,
    message: str,
    recoverable: bool,
    reason: str,
) -> ErrorEnvelope:
    return ErrorEnvelope(
        schema_version=SCHEMA_VERSION,
        trace_id=trace_id,
        error_id=error_id,
        code=code,
        message=message,
        recoverable=recoverable,
        source="local_api",
        details={"reason": reason},
    )


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
