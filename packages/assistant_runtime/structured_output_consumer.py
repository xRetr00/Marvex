from __future__ import annotations

import json
import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ConsumptionStatus = Literal[
    "accepted_for_future_stage",
    "rejected_invalid_structured_payload",
    "rejected_provider_error",
    "rejected_provider_timeout",
    "rejected_refusal_unresolved",
    "rejected_incomplete_unresolved",
]


_CONSUMPTION_STATUS_BY_HANDOFF_STATUS: dict[str, ConsumptionStatus] = {
    "usable_structured_payload": "accepted_for_future_stage",
    "invalid_structured_payload": "rejected_invalid_structured_payload",
    "provider_error": "rejected_provider_error",
    "provider_timeout": "rejected_provider_timeout",
    "refusal_unresolved": "rejected_refusal_unresolved",
    "incomplete_unresolved": "rejected_incomplete_unresolved",
}
_ERROR_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
_FORBIDDEN_ERROR_CODE_PARTS = {"SECRET", "PASSWORD", "TOKEN", "API_KEY", "BEARER"}
_FORBIDDEN_MESSAGE_TERMS = (
    "api key",
    "api_key",
    "authorization",
    "bearer",
    "exception",
    "full prompt",
    "jsondecodeerror",
    "password",
    "provider response id",
    "runtimeerror",
    "secret",
    "session id",
    "system prompt",
    "thread id",
    "token",
    "traceback",
    "validationerror",
)
_FORBIDDEN_KEY_NAMES = {
    "api_key",
    "auth",
    "authorization",
    "bearer",
    "conversation",
    "conversation_id",
    "full_prompt",
    "messages",
    "password",
    "previous_response_id",
    "prompt",
    "provider_id",
    "provider_raw",
    "provider_response_id",
    "raw_metadata",
    "raw_output",
    "raw_provider_output",
    "raw_response",
    "response_id",
    "secret",
    "session_id",
    "system_prompt",
    "thread_id",
    "token",
    "transcript",
}


class AssistantStructuredOutputInputDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    source_state: str = Field(..., min_length=1)
    handoff_status: str = Field(..., min_length=1)
    target_contract: str = Field(..., min_length=1)
    sanitized_message: str = Field(..., min_length=1)
    sanitized_error_code: str | None = None
    parsed_payload: Any | None = None
    diagnostic_only: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "schema_version",
        "trace_id",
        "turn_id",
        "source_state",
        "handoff_status",
        "target_contract",
        "sanitized_message",
    )
    @classmethod
    def _reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("identity and status fields must not be blank")
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

    @field_validator("sanitized_error_code")
    @classmethod
    def _validate_sanitized_error_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value or _ERROR_CODE_PATTERN.fullmatch(value) is None:
            raise ValueError("sanitized_error_code must be stable uppercase snake case")
        if any(part in value for part in _FORBIDDEN_ERROR_CODE_PARTS):
            raise ValueError("sanitized_error_code must not carry secret markers")
        return value

    @field_validator("parsed_payload")
    @classmethod
    def _validate_parsed_payload(cls, value: Any) -> Any:
        if value is None:
            return value
        _ensure_json_compatible(value, "parsed_payload")
        _reject_forbidden_keys(value)
        return value

    @field_validator("metadata")
    @classmethod
    def _validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        _ensure_json_compatible(value, "metadata")
        _reject_forbidden_keys(value)
        return value

    @model_validator(mode="after")
    def _validate_payload_status(self) -> "AssistantStructuredOutputInputDraft":
        accepted = self.handoff_status == "usable_structured_payload"
        if accepted and self.parsed_payload is None:
            raise ValueError("usable structured payload requires parsed_payload")
        if not accepted and self.parsed_payload is not None:
            raise ValueError("non-usable structured output must not carry parsed_payload")
        return self


class AssistantStructuredOutputConsumptionDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(..., min_length=1)
    trace_id: str = Field(..., min_length=1)
    turn_id: str = Field(..., min_length=1)
    source_state: str = Field(..., min_length=1)
    handoff_status: str = Field(..., min_length=1)
    target_contract: str = Field(..., min_length=1)
    consumption_status: ConsumptionStatus
    sanitized_message: str = Field(..., min_length=1)
    sanitized_error_code: str | None = None
    parsed_payload: Any | None = None
    diagnostic_only: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    safe_for_user_facing_final_response: Literal[False] = False

    @field_validator(
        "schema_version",
        "trace_id",
        "turn_id",
        "source_state",
        "handoff_status",
        "target_contract",
        "sanitized_message",
    )
    @classmethod
    def _reject_blank_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("identity and status fields must not be blank")
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

    @field_validator("sanitized_error_code")
    @classmethod
    def _validate_sanitized_error_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value or _ERROR_CODE_PATTERN.fullmatch(value) is None:
            raise ValueError("sanitized_error_code must be stable uppercase snake case")
        if any(part in value for part in _FORBIDDEN_ERROR_CODE_PARTS):
            raise ValueError("sanitized_error_code must not carry secret markers")
        return value

    @field_validator("parsed_payload")
    @classmethod
    def _validate_parsed_payload(cls, value: Any) -> Any:
        if value is None:
            return value
        _ensure_json_compatible(value, "parsed_payload")
        _reject_forbidden_keys(value)
        return value

    @field_validator("metadata")
    @classmethod
    def _validate_metadata(cls, value: dict[str, Any]) -> dict[str, Any]:
        _ensure_json_compatible(value, "metadata")
        _reject_forbidden_keys(value)
        return value

    @model_validator(mode="after")
    def _validate_consumed_payload(self) -> "AssistantStructuredOutputConsumptionDraft":
        if (
            self.consumption_status != "accepted_for_future_stage"
            and self.parsed_payload is not None
        ):
            raise ValueError("rejected structured output must not carry parsed_payload")
        if self.safe_for_user_facing_final_response is not False:
            raise ValueError("structured output seam is not user-facing")
        return self


def consume_structured_output_handoff_draft(
    draft: AssistantStructuredOutputInputDraft,
) -> AssistantStructuredOutputConsumptionDraft:
    consumption_status = _CONSUMPTION_STATUS_BY_HANDOFF_STATUS.get(draft.handoff_status)
    if consumption_status is None:
        raise ValueError(f"unsupported structured output status: {draft.handoff_status}")
    if consumption_status == "accepted_for_future_stage" and draft.diagnostic_only:
        raise ValueError("diagnostic structured output is not accepted as usable data")

    parsed_payload = (
        draft.parsed_payload
        if consumption_status == "accepted_for_future_stage"
        else None
    )
    return AssistantStructuredOutputConsumptionDraft(
        schema_version=draft.schema_version,
        trace_id=draft.trace_id,
        turn_id=draft.turn_id,
        source_state=draft.source_state,
        handoff_status=draft.handoff_status,
        target_contract=draft.target_contract,
        consumption_status=consumption_status,
        sanitized_message=draft.sanitized_message,
        sanitized_error_code=draft.sanitized_error_code,
        parsed_payload=parsed_payload,
        diagnostic_only=draft.diagnostic_only,
        metadata=dict(draft.metadata),
        safe_for_user_facing_final_response=False,
    )


def _ensure_json_compatible(value: Any, field_name: str) -> None:
    try:
        json.dumps(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be JSON-compatible") from exc


def _reject_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            normalized = _normalize_key(str(key))
            if normalized in _FORBIDDEN_KEY_NAMES:
                raise ValueError("structured output input contains unsafe key")
            _reject_forbidden_keys(item)
        return
    if isinstance(value, list):
        for item in value:
            _reject_forbidden_keys(item)


def _normalize_key(value: str) -> str:
    camel_split = re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", value)
    separated = re.sub(r"[^A-Za-z0-9]+", "_", camel_split)
    return separated.strip("_").lower()


def _looks_like_full_json(value: str) -> bool:
    stripped = value.strip()
    return (
        (stripped.startswith("{") and stripped.endswith("}"))
        or (stripped.startswith("[") and stripped.endswith("]"))
    )
