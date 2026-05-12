from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .fallback_result import (
    MAX_RAW_PREVIEW_LENGTH,
    FallbackState,
    StructuredOutputFallbackResult,
    _reject_forbidden_metadata_keys,
)


HandoffStatus = Literal[
    "usable_structured_payload",
    "invalid_structured_payload",
    "provider_error",
    "provider_timeout",
    "refusal_unresolved",
    "incomplete_unresolved",
]


_HANDOFF_STATUS_BY_STATE: dict[FallbackState, HandoffStatus] = {
    "valid_structured_result": "usable_structured_payload",
    "invalid_structured_output": "invalid_structured_payload",
    "provider_error": "provider_error",
    "provider_timeout": "provider_timeout",
    "refusal_unresolved_or_provider_specific": "refusal_unresolved",
    "incomplete_unresolved_or_provider_specific": "incomplete_unresolved",
}
_ERROR_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
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


class StructuredOutputHandoffDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    state: FallbackState
    target_contract: str = Field(..., min_length=1)
    handoff_status: HandoffStatus
    sanitized_message: str = Field(..., min_length=1)
    sanitized_error_code: str | None
    parsed_payload: Any | None
    raw_preview: str | None = Field(default=None, max_length=MAX_RAW_PREVIEW_LENGTH)
    diagnostic_only: bool
    safe_for_user_facing_final_response: Literal[False] = False

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

    @field_validator("parsed_payload")
    @classmethod
    def _validate_parsed_payload(cls, value: Any) -> Any:
        if value is None:
            return value
        try:
            json.dumps(value)
        except (TypeError, ValueError) as exc:
            raise ValueError("parsed_payload must be JSON-compatible") from exc
        _reject_forbidden_metadata_keys(value)
        return value

    @model_validator(mode="after")
    def _validate_payload_status(self) -> "StructuredOutputHandoffDraft":
        if self.state == "valid_structured_result":
            if self.handoff_status != "usable_structured_payload":
                raise ValueError("valid structured output requires usable handoff status")
            if self.parsed_payload is None:
                raise ValueError("valid structured output requires parsed payload")
            return self
        if self.parsed_payload is not None:
            raise ValueError("non-valid structured output must not carry parsed payload")
        return self


def build_structured_output_handoff_draft(
    result: StructuredOutputFallbackResult,
) -> StructuredOutputHandoffDraft:
    handoff_status = _HANDOFF_STATUS_BY_STATE.get(result.state)
    if handoff_status is None:
        raise ValueError(f"unsupported structured output state: {result.state}")
    parsed_payload = (
        result.parsed_payload if result.state == "valid_structured_result" else None
    )
    return StructuredOutputHandoffDraft(
        schema_version=result.schema_version,
        trace_id=result.trace_id,
        turn_id=result.turn_id,
        state=result.state,
        target_contract=result.target_contract,
        handoff_status=handoff_status,
        sanitized_message=result.sanitized_message,
        sanitized_error_code=result.sanitized_error_code,
        parsed_payload=parsed_payload,
        raw_preview=result.raw_preview,
        diagnostic_only=result.raw_preview is not None,
        safe_for_user_facing_final_response=False,
    )


def _looks_like_full_json(value: str) -> bool:
    stripped = value.strip()
    return (
        (stripped.startswith("{") and stripped.endswith("}"))
        or (stripped.startswith("[") and stripped.endswith("]"))
    )
