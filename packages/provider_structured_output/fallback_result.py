from __future__ import annotations

import json
import re
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator


DEFAULT_SCHEMA_VERSION = "0.1.1-draft"
MAX_RAW_PREVIEW_LENGTH = 300
_ERROR_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
_FORBIDDEN_METADATA_KEYS = {
    "rawoutput",
    "rawprovideroutput",
    "rawresponse",
    "rawmetadata",
    "providerraw",
    "prompt",
    "fullprompt",
    "systemprompt",
    "messages",
    "conversation",
    "transcript",
    "providerresponseid",
    "previousresponseid",
    "responseid",
    "sessionid",
    "conversationid",
    "threadid",
    "auth",
    "apikey",
    "authorization",
    "bearer",
    "token",
    "secret",
    "password",
}
_FORBIDDEN_METADATA_KEY_PARTS = (
    "apikey",
    "authorization",
    "bearer",
    "password",
    "secret",
    "token",
)
_FORBIDDEN_ERROR_CODE_PARTS = {"SECRET", "PASSWORD", "TOKEN", "API_KEY", "BEARER"}
_FORBIDDEN_MESSAGE_TERMS = (
    "api_key",
    "authorization",
    "bearer",
    "exception",
    "full prompt",
    "jsondecodeerror",
    "password",
    "runtimeerror",
    "secret",
    "system prompt",
    "token",
    "traceback",
    "validationerror",
)
TargetModel = TypeVar("TargetModel", bound=BaseModel)

FallbackState = Literal[
    "valid_structured_result",
    "invalid_structured_output",
    "provider_error",
    "provider_timeout",
    "refusal_unresolved_or_provider_specific",
    "incomplete_unresolved_or_provider_specific",
]


class StructuredOutputFallbackResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    state: FallbackState
    target_contract: str = Field(..., min_length=1)
    sanitized_message: str = Field(..., min_length=1)
    sanitized_error_code: str | None
    parsed_payload: Any | None
    raw_preview: str | None = Field(default=None, max_length=MAX_RAW_PREVIEW_LENGTH)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("sanitized_error_code")
    @classmethod
    def _validate_error_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value or _ERROR_CODE_PATTERN.fullmatch(value) is None:
            raise ValueError("sanitized_error_code must be stable uppercase snake case")
        if any(part in value for part in _FORBIDDEN_ERROR_CODE_PARTS):
            raise ValueError("sanitized_error_code must not carry secret markers")
        return value

    @field_validator("sanitized_message")
    @classmethod
    def _validate_sanitized_message(cls, value: str) -> str:
        lowered = value.lower()
        if _looks_like_full_json(value) or any(
            term in lowered for term in _FORBIDDEN_MESSAGE_TERMS
        ):
            raise ValueError("sanitized_message must not carry raw or secret text")
        return value

    @field_validator("parsed_payload", "metadata")
    @classmethod
    def _validate_json_compatible(cls, value: Any) -> Any:
        if value is None:
            return value
        try:
            json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("value must be JSON-compatible") from exc
        return value

    @field_validator("metadata")
    @classmethod
    def _validate_metadata_keys(cls, value: dict[str, Any]) -> dict[str, Any]:
        _reject_forbidden_metadata_keys(value)
        return value

    @model_validator(mode="after")
    def _validate_state_payload(self) -> "StructuredOutputFallbackResult":
        if self.state == "valid_structured_result" and self.parsed_payload is None:
            raise ValueError("valid_structured_result requires parsed_payload")
        return self


def create_valid_structured_result(
    *,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
    trace_id: str,
    turn_id: str,
    target_contract: str,
    parsed_payload: dict[str, Any],
    metadata: dict[str, Any] | None = None,
) -> StructuredOutputFallbackResult:
    return StructuredOutputFallbackResult(
        schema_version=schema_version,
        trace_id=trace_id,
        turn_id=turn_id,
        state="valid_structured_result",
        target_contract=target_contract,
        sanitized_message="Structured output validated.",
        sanitized_error_code=None,
        parsed_payload=parsed_payload,
        raw_preview=None,
        metadata=dict(metadata or {}),
    )


def create_invalid_structured_output(
    *,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
    trace_id: str,
    turn_id: str,
    target_contract: str,
    sanitized_error_code: str = "INVALID_STRUCTURED_OUTPUT",
    sanitized_message: str | None = None,
    validation_error: ValidationError | None = None,
    raw_preview: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> StructuredOutputFallbackResult:
    message = sanitized_message
    if message is None:
        message = (
            "Structured output failed target validation."
            if validation_error is not None
            else "Structured output was invalid."
        )
    code = "VALIDATION_FAILED" if validation_error is not None else sanitized_error_code
    return StructuredOutputFallbackResult(
        schema_version=schema_version,
        trace_id=trace_id,
        turn_id=turn_id,
        state="invalid_structured_output",
        target_contract=target_contract,
        sanitized_message=message,
        sanitized_error_code=code,
        parsed_payload=None,
        raw_preview=raw_preview,
        metadata=dict(metadata or {}),
    )


def validate_raw_structured_output(
    *,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
    trace_id: str,
    turn_id: str,
    target_contract: str,
    raw_output_text: str,
    target_model: type[TargetModel],
    include_raw_preview: bool = False,
) -> StructuredOutputFallbackResult:
    raw_preview = _bounded_raw_preview(raw_output_text, include_raw_preview)

    if not raw_output_text.strip():
        return create_invalid_structured_output(
            schema_version=schema_version,
            trace_id=trace_id,
            turn_id=turn_id,
            target_contract=target_contract,
            sanitized_error_code="EMPTY_STRUCTURED_OUTPUT",
            sanitized_message="Structured output was empty.",
            raw_preview=raw_preview,
        )

    try:
        payload = json.loads(raw_output_text)
    except json.JSONDecodeError:
        return create_invalid_structured_output(
            schema_version=schema_version,
            trace_id=trace_id,
            turn_id=turn_id,
            target_contract=target_contract,
            sanitized_error_code="INVALID_JSON",
            sanitized_message="Structured output was not valid JSON.",
            raw_preview=raw_preview,
        )

    try:
        parsed = target_model.model_validate(payload)
    except ValidationError as exc:
        return create_invalid_structured_output(
            schema_version=schema_version,
            trace_id=trace_id,
            turn_id=turn_id,
            target_contract=target_contract,
            validation_error=exc,
            raw_preview=raw_preview,
        )

    return create_valid_structured_result(
        schema_version=schema_version,
        trace_id=trace_id,
        turn_id=turn_id,
        target_contract=target_contract,
        parsed_payload=parsed.model_dump(),
    )


def _bounded_raw_preview(raw_output_text: str, include_raw_preview: bool) -> str | None:
    if not include_raw_preview:
        return None
    return raw_output_text[:MAX_RAW_PREVIEW_LENGTH]


def create_provider_error(
    *,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
    trace_id: str,
    turn_id: str,
    target_contract: str,
    error: object | None = None,
    metadata: dict[str, Any] | None = None,
) -> StructuredOutputFallbackResult:
    return StructuredOutputFallbackResult(
        schema_version=schema_version,
        trace_id=trace_id,
        turn_id=turn_id,
        state="provider_error",
        target_contract=target_contract,
        sanitized_message="Provider error occurred.",
        sanitized_error_code="PROVIDER_ERROR",
        parsed_payload=None,
        raw_preview=None,
        metadata=dict(metadata or {}),
    )


def create_provider_timeout(
    *,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
    trace_id: str,
    turn_id: str,
    target_contract: str,
    metadata: dict[str, Any] | None = None,
) -> StructuredOutputFallbackResult:
    return StructuredOutputFallbackResult(
        schema_version=schema_version,
        trace_id=trace_id,
        turn_id=turn_id,
        state="provider_timeout",
        target_contract=target_contract,
        sanitized_message="Provider request timed out.",
        sanitized_error_code="PROVIDER_TIMEOUT",
        parsed_payload=None,
        raw_preview=None,
        metadata=dict(metadata or {}),
    )


def _looks_like_full_json(value: str) -> bool:
    stripped = value.strip()
    return (
        (stripped.startswith("{") and stripped.endswith("}"))
        or (stripped.startswith("[") and stripped.endswith("]"))
    )


def _normalized_key(value: object) -> str:
    text = str(value)
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _reject_forbidden_metadata_keys(value: object) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = _normalized_key(key)
            if normalized in _FORBIDDEN_METADATA_KEYS or any(
                part in normalized for part in _FORBIDDEN_METADATA_KEY_PARTS
            ):
                raise ValueError("metadata contains a forbidden key")
            _reject_forbidden_metadata_keys(item)
    elif isinstance(value, list):
        for item in value:
            _reject_forbidden_metadata_keys(item)


def create_refusal_unresolved(
    *,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
    trace_id: str,
    turn_id: str,
    target_contract: str,
    metadata: dict[str, Any] | None = None,
) -> StructuredOutputFallbackResult:
    return StructuredOutputFallbackResult(
        schema_version=schema_version,
        trace_id=trace_id,
        turn_id=turn_id,
        state="refusal_unresolved_or_provider_specific",
        target_contract=target_contract,
        sanitized_message="Refusal-like provider behavior is unresolved.",
        sanitized_error_code="REFUSAL_UNRESOLVED",
        parsed_payload=None,
        raw_preview=None,
        metadata=dict(metadata or {}),
    )


def create_incomplete_unresolved(
    *,
    schema_version: str = DEFAULT_SCHEMA_VERSION,
    trace_id: str,
    turn_id: str,
    target_contract: str,
    metadata: dict[str, Any] | None = None,
) -> StructuredOutputFallbackResult:
    return StructuredOutputFallbackResult(
        schema_version=schema_version,
        trace_id=trace_id,
        turn_id=turn_id,
        state="incomplete_unresolved_or_provider_specific",
        target_contract=target_contract,
        sanitized_message="Incomplete provider behavior is unresolved.",
        sanitized_error_code="INCOMPLETE_UNRESOLVED",
        parsed_payload=None,
        raw_preview=None,
        metadata=dict(metadata or {}),
    )
