from __future__ import annotations

from collections.abc import Mapping
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from packages.contracts import ErrorCode, ErrorEnvelope


TargetModel = TypeVar("TargetModel", bound=BaseModel)

DEFAULT_SCHEMA_VERSION = "0.1.1-draft"
ERROR_SOURCE = "provider_structured_output"


def validate_structured_payload(
    payload: object,
    target_model: type[TargetModel],
    *,
    trace_id: str | None = None,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
) -> TargetModel | ErrorEnvelope:
    """Validate already-structured payload data into a Marvex contract model."""
    data = _payload_data(payload)
    effective_trace_id = _trace_id(data, trace_id)

    try:
        return target_model.model_validate(data)
    except ValidationError as exc:
        return ErrorEnvelope(
            schema_version=schema_version,
            trace_id=effective_trace_id,
            error_id="structured-output-validation-error",
            code=ErrorCode.VALIDATION_ERROR,
            message="Structured payload validation failed.",
            recoverable=False,
            source=ERROR_SOURCE,
            details={
                "target": target_model.__name__,
                "errors": _validation_errors(exc),
            },
        )


def validate_structured_result(
    result: object,
    target_model: type[TargetModel],
    *,
    trace_id: str | None = None,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
) -> TargetModel | ErrorEnvelope:
    data = _payload_data(result)
    effective_trace_id = _trace_id(data, trace_id)
    payload = _field_value(data, "structured_payload")

    if payload is None:
        return ErrorEnvelope(
            schema_version=schema_version,
            trace_id=effective_trace_id,
            error_id="structured-output-missing-payload",
            code=ErrorCode.VALIDATION_ERROR,
            message="Structured payload is missing.",
            recoverable=False,
            source=ERROR_SOURCE,
            details={
                "target": target_model.__name__,
                "field": "structured_payload",
            },
        )

    return validate_structured_payload(
        payload,
        target_model,
        trace_id=effective_trace_id,
        schema_version=schema_version,
    )


def _payload_data(payload: object) -> object:
    if isinstance(payload, BaseModel):
        return payload.model_dump()
    if isinstance(payload, Mapping):
        return dict(payload)
    if hasattr(payload, "model_dump"):
        return payload.model_dump()
    if hasattr(payload, "__dict__"):
        return {
            key: value
            for key, value in vars(payload).items()
            if not key.startswith("_")
        }
    return payload


def _trace_id(data: object, fallback: str | None) -> str:
    if fallback:
        return fallback
    if isinstance(data, Mapping):
        candidate = data.get("trace_id")
        if isinstance(candidate, str) and candidate:
            return candidate
    return "trace-unavailable"


def _field_value(data: object, field_name: str) -> object:
    if isinstance(data, Mapping):
        return data.get(field_name)
    return getattr(data, field_name, None)


def _validation_errors(exc: ValidationError) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    for error in exc.errors():
        location = ".".join(str(part) for part in error["loc"]) or "<root>"
        errors.append(
            {
                "loc": location,
                "msg": str(error["msg"]),
                "type": str(error["type"]),
            }
        )
    return errors
