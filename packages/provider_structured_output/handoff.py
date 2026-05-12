from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .fallback_result import MAX_RAW_PREVIEW_LENGTH, FallbackState, StructuredOutputFallbackResult


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
    parsed_payload = (
        result.parsed_payload if result.state == "valid_structured_result" else None
    )
    return StructuredOutputHandoffDraft(
        schema_version=result.schema_version,
        trace_id=result.trace_id,
        turn_id=result.turn_id,
        state=result.state,
        target_contract=result.target_contract,
        handoff_status=_HANDOFF_STATUS_BY_STATE[result.state],
        sanitized_message=result.sanitized_message,
        sanitized_error_code=result.sanitized_error_code,
        parsed_payload=parsed_payload,
        raw_preview=result.raw_preview,
        diagnostic_only=result.raw_preview is not None,
        safe_for_user_facing_final_response=False,
    )
