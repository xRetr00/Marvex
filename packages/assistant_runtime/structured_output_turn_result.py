from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from packages.contracts import (
    AssistantFinalResponse,
    AssistantTurnResult,
    ErrorCode,
    ErrorEnvelope,
    StageStatus,
    TraceLevel,
    TraceStage,
)
from packages.telemetry import TelemetrySink, make_trace_event

from .result_assembly import build_stage_summary
from .structured_output_runtime_entry import consume_structured_output_for_future_stage


ERROR_ID_SUFFIX = "structured-output-consumption"
STRUCTURED_OUTPUT_STAGE = "structured_output_consumption"

_ERROR_CODE_BY_CONSUMPTION_STATUS = {
    "rejected_invalid_structured_payload": ErrorCode.VALIDATION_ERROR,
    "rejected_provider_error": ErrorCode.PROVIDER_ERROR,
    "rejected_provider_timeout": ErrorCode.PROVIDER_TIMEOUT,
    "rejected_refusal_unresolved": ErrorCode.PROVIDER_ERROR,
    "rejected_incomplete_unresolved": ErrorCode.PROVIDER_ERROR,
}


def consume_structured_output_as_turn_result(
    handoff_input: dict[str, Any],
    *,
    telemetry_sink: TelemetrySink | None = None,
) -> AssistantTurnResult:
    trace_id = _text_field(handoff_input, "trace_id", "trace-unavailable")
    turn_id = _text_field(handoff_input, "turn_id", "turn-unavailable")
    schema_version = _text_field(handoff_input, "schema_version", "0.1.1-draft")

    try:
        consumed = consume_structured_output_for_future_stage(dict(handoff_input))
    except (TypeError, ValueError, ValidationError):
        _emit_structured_output_trace(
            telemetry_sink=telemetry_sink,
            schema_version=schema_version,
            trace_id=trace_id,
            turn_id=turn_id,
            data={
                **_dict_or_empty(handoff_input),
                "consumption_status": "rejected_invalid_structured_payload",
                "sanitized_message": "Structured output handoff was invalid.",
                "sanitized_error_code": ErrorCode.VALIDATION_ERROR.value,
            },
            level=TraceLevel.ERROR,
        )
        return _error_result(
            schema_version=schema_version,
            trace_id=trace_id,
            turn_id=turn_id,
            code=ErrorCode.VALIDATION_ERROR,
            message="Structured output handoff was invalid.",
        )

    trace_data = consumed.model_dump(exclude_none=True)
    if consumed.consumption_status != "accepted_for_future_stage":
        code = _ERROR_CODE_BY_CONSUMPTION_STATUS[consumed.consumption_status]
        _emit_structured_output_trace(
            telemetry_sink=telemetry_sink,
            schema_version=consumed.schema_version,
            trace_id=consumed.trace_id,
            turn_id=consumed.turn_id,
            data=trace_data,
            level=TraceLevel.ERROR,
        )
        return _error_result(
            schema_version=consumed.schema_version,
            trace_id=consumed.trace_id,
            turn_id=consumed.turn_id,
            code=code,
            message=consumed.sanitized_message,
        )

    try:
        final_response = AssistantFinalResponse.model_validate(consumed.parsed_payload)
    except ValidationError:
        _emit_structured_output_trace(
            telemetry_sink=telemetry_sink,
            schema_version=consumed.schema_version,
            trace_id=consumed.trace_id,
            turn_id=consumed.turn_id,
            data={
                **trace_data,
                "consumption_status": "rejected_invalid_structured_payload",
                "sanitized_message": "Structured output final response was invalid.",
                "sanitized_error_code": ErrorCode.VALIDATION_ERROR.value,
            },
            level=TraceLevel.ERROR,
        )
        return _error_result(
            schema_version=consumed.schema_version,
            trace_id=consumed.trace_id,
            turn_id=consumed.turn_id,
            code=ErrorCode.VALIDATION_ERROR,
            message="Structured output final response was invalid.",
        )

    _emit_structured_output_trace(
        telemetry_sink=telemetry_sink,
        schema_version=consumed.schema_version,
        trace_id=consumed.trace_id,
        turn_id=consumed.turn_id,
        data=trace_data,
        level=TraceLevel.INFO,
    )
    return AssistantTurnResult(
        schema_version=consumed.schema_version,
        trace_id=consumed.trace_id,
        turn_id=consumed.turn_id,
        assistant_final_response=final_response,
        output_events=[],
        stage_summaries=[
            build_stage_summary(
                stage_name=STRUCTURED_OUTPUT_STAGE,
                status=StageStatus.COMPLETED,
            ),
            build_stage_summary(
                stage_name="final_response_assembly",
                status=StageStatus.COMPLETED,
            ),
        ],
        provider_turn_refs=[],
        tool_result_refs=[],
        memory_result_refs=[],
        session_result_ref=None,
        error=None,
        metadata={},
    )


def _error_result(
    *,
    schema_version: str,
    trace_id: str,
    turn_id: str,
    code: ErrorCode,
    message: str,
) -> AssistantTurnResult:
    error_id = f"{turn_id}:{ERROR_ID_SUFFIX}"
    error = ErrorEnvelope(
        schema_version=schema_version,
        trace_id=trace_id,
        error_id=error_id,
        code=code,
        message=message,
        recoverable=False,
        source="assistant_runtime",
        details={},
    )
    return AssistantTurnResult(
        schema_version=schema_version,
        trace_id=trace_id,
        turn_id=turn_id,
        assistant_final_response=None,
        output_events=[],
        stage_summaries=[
            build_stage_summary(
                stage_name=STRUCTURED_OUTPUT_STAGE,
                status=StageStatus.FAILED,
                error_ref=error_id,
            )
        ],
        provider_turn_refs=[],
        tool_result_refs=[],
        memory_result_refs=[],
        session_result_ref=None,
        error=error,
        metadata={},
    )


def _emit_structured_output_trace(
    *,
    telemetry_sink: TelemetrySink | None,
    schema_version: str,
    trace_id: str,
    turn_id: str,
    data: dict[str, Any],
    level: TraceLevel,
) -> None:
    if telemetry_sink is None:
        return
    telemetry_sink.emit(
        make_trace_event(
            schema_version=schema_version,
            trace_id=trace_id,
            turn_id=turn_id,
            stage=TraceStage.FINAL_RESPONSE_CREATED,
            level=level,
            message="Structured output consumption recorded.",
            data=data,
        )
    )


def _text_field(value: object, field_name: str, fallback: str) -> str:
    if isinstance(value, dict):
        candidate = value.get(field_name)
        if isinstance(candidate, str) and candidate.strip():
            return candidate
    return fallback


def _dict_or_empty(value: object) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}
