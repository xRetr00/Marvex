from __future__ import annotations

import json
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from packages.contracts import AssistantTurnInput, ErrorCode, ErrorEnvelope
from packages.process_runtime import HealthVersionProvider

from .auth_policy import validate_local_bearer_token
from .contracts import (
    LOCAL_TRACES_PREFIX,
    LOCAL_TURN_REQUEST_FIELDS,
    LOCAL_TURNS_EXECUTION_MODE,
    LOCAL_TURNS_PATH,
    SCHEMA_VERSION,
    LocalTurnRequestEnvelope,
    TraceReader,
    TurnHandler,
)


def create_local_api_asgi_app(
    provider: HealthVersionProvider,
    *,
    turn_handler: TurnHandler | None = None,
    trace_reader: TraceReader | None = None,
    local_auth_token: str | None = None,
    accepted_turn_execution_modes: tuple[str, ...] = (LOCAL_TURNS_EXECUTION_MODE,),
) -> FastAPI:
    app = FastAPI(title="Marvex Core API", docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/health", response_model=None)
    async def health() -> JSONResponse:
        return _json(provider.get_health().model_dump(mode="json"))

    @app.get("/version", response_model=None)
    async def version() -> JSONResponse:
        return _json(provider.get_version().model_dump(mode="json"))

    @app.post(LOCAL_TURNS_PATH, response_model=None)
    async def turns(request: Request) -> JSONResponse:
        auth_error = validate_local_bearer_token(
            authorization_header=request.headers.get("authorization"),
            expected_token=local_auth_token or "",
            trace_id="trace-local-api-auth-required",
        )
        if auth_error is not None:
            return _json(auth_error.model_dump(mode="json"), status_code=401)
        if turn_handler is None:
            return _json(
                _error_envelope(
                    trace_id="trace-local-api-turn-handler-unavailable",
                    error_id="local-api-turn-handler-unavailable",
                    code=ErrorCode.SERVICE_UNHEALTHY,
                    message="Local API turn handler unavailable.",
                    recoverable=True,
                    reason="handler_unavailable",
                ).model_dump(mode="json"),
                status_code=503,
            )
        parsed = await _parse_turn_request(request, accepted_turn_execution_modes=accepted_turn_execution_modes)
        if isinstance(parsed, ErrorEnvelope):
            return _json(parsed.model_dump(mode="json"), status_code=400)
        try:
            result = turn_handler(parsed)
        except Exception:
            return _json(
                _error_envelope(
                    trace_id=parsed.assistant_turn_input.trace_id,
                    error_id="local-api-turn-handler-failed",
                    code=ErrorCode.INTERNAL_ERROR,
                    message="Local API turn handler failed.",
                    recoverable=False,
                    reason="handler_failure",
                ).model_dump(mode="json"),
                status_code=500,
            )
        return _json(result.model_dump(mode="json"))

    @app.get(f"{LOCAL_TRACES_PREFIX}{{trace_id:path}}", response_model=None)
    async def trace(trace_id: str, request: Request) -> JSONResponse:
        auth_error = validate_local_bearer_token(
            authorization_header=request.headers.get("authorization"),
            expected_token=local_auth_token or "",
            trace_id="trace-local-api-auth-required",
        )
        if auth_error is not None:
            return _json(auth_error.model_dump(mode="json"), status_code=401)
        if not _valid_trace_id(trace_id):
            return _json(
                _error_envelope(
                    trace_id="trace-local-api-validation-error",
                    error_id="local-api-trace-validation-error",
                    code=ErrorCode.VALIDATION_ERROR,
                    message="Local API trace request validation failed.",
                    recoverable=False,
                    reason="invalid_trace_id",
                ).model_dump(mode="json"),
                status_code=400,
            )
        if trace_reader is None:
            return _json(
                _error_envelope(
                    trace_id=trace_id,
                    error_id="local-api-trace-reader-unavailable",
                    code=ErrorCode.SERVICE_UNHEALTHY,
                    message="Local API trace reader unavailable.",
                    recoverable=True,
                    reason="trace_reader_unavailable",
                ).model_dump(mode="json"),
                status_code=503,
            )
        try:
            envelope = trace_reader.read_trace(trace_id)
        except Exception:
            return _json(
                _error_envelope(
                    trace_id=trace_id,
                    error_id="local-api-trace-reader-failed",
                    code=ErrorCode.INTERNAL_ERROR,
                    message="Local API trace reader failed.",
                    recoverable=False,
                    reason="trace_reader_failure",
                ).model_dump(mode="json"),
                status_code=500,
            )
        if envelope is None:
            return _json(
                _error_envelope(
                    trace_id=trace_id,
                    error_id="local-api-trace-not-found",
                    code=ErrorCode.NOT_FOUND,
                    message="Local API trace not found.",
                    recoverable=False,
                    reason="trace_not_found",
                ).model_dump(mode="json"),
                status_code=404,
            )
        try:
            json.dumps(envelope)
        except Exception:
            return _json(
                _error_envelope(
                    trace_id=trace_id,
                    error_id="local-api-trace-reader-failed",
                    code=ErrorCode.INTERNAL_ERROR,
                    message="Local API trace reader failed.",
                    recoverable=False,
                    reason="trace_reader_failure",
                ).model_dump(mode="json"),
                status_code=500,
            )
        return _json(envelope)

    @app.api_route("/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"], response_model=None)
    async def not_found(path: str) -> JSONResponse:
        return _json(
            ErrorEnvelope(
                schema_version=SCHEMA_VERSION,
                trace_id="trace-local-api-not-found",
                error_id="local-api-not-found",
                code=ErrorCode.NOT_FOUND,
                message="Endpoint not found.",
                recoverable=False,
                source="local_api",
                details={"path": f"/{path}"},
            ).model_dump(mode="json"),
            status_code=404,
        )

    return app


async def _parse_turn_request(
    request: Request,
    *,
    accepted_turn_execution_modes: tuple[str, ...],
) -> LocalTurnRequestEnvelope | ErrorEnvelope:
    try:
        payload = await request.json()
    except Exception:
        return _validation_error("invalid_json")
    if not isinstance(payload, dict):
        return _validation_error("request_must_be_object")
    if set(payload) != LOCAL_TURN_REQUEST_FIELDS:
        return _validation_error("invalid_request_fields")
    if payload["schema_version"] != SCHEMA_VERSION:
        return _validation_error("invalid_schema_version")
    if payload["execution_mode"] not in accepted_turn_execution_modes:
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


def _valid_trace_id(trace_id: str) -> bool:
    if not trace_id.strip():
        return False
    return all(character.isalnum() or character in ".:-_" for character in trace_id)


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


def _json(payload: dict[str, Any], *, status_code: int = 200) -> JSONResponse:
    return JSONResponse(status_code=status_code, content=payload)
