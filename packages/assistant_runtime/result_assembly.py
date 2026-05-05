from __future__ import annotations

from typing import Any

from packages.contracts import (
    AssistantFinalResponse,
    AssistantFinishReason,
    AssistantResponseType,
    AssistantTurnResult,
    ErrorCode,
    ErrorEnvelope,
    OutputChannelIntent,
    StageStatus,
    StageSummary,
)


def build_text_final_response(
    *,
    schema_version: str,
    text: str,
    output_channel_intent: OutputChannelIntent = OutputChannelIntent.DEFAULT,
    finish_reason: AssistantFinishReason = AssistantFinishReason.STOP,
    safe_for_display: bool = True,
    safe_for_speech: bool = True,
    metadata: dict[str, Any] | None = None,
) -> AssistantFinalResponse:
    return AssistantFinalResponse(
        schema_version=schema_version,
        response_type=AssistantResponseType.TEXT,
        text=text,
        payload_ref=None,
        output_channel_intent=output_channel_intent,
        safe_for_display=safe_for_display,
        safe_for_speech=safe_for_speech,
        memory_write_candidate_hint=False,
        finish_reason=finish_reason,
        metadata=dict(metadata or {}),
    )


def build_stage_summary(
    *,
    stage_name: str,
    status: StageStatus,
    error_ref: str | None = None,
) -> StageSummary:
    return StageSummary(
        stage_name=stage_name,
        status=status,
        started_at=None,
        completed_at=None,
        ref=None,
        error_ref=error_ref,
    )


def build_text_success_turn_result(
    *,
    schema_version: str,
    trace_id: str,
    turn_id: str,
    text: str,
    metadata: dict[str, Any] | None = None,
) -> AssistantTurnResult:
    return AssistantTurnResult(
        schema_version=schema_version,
        trace_id=trace_id,
        turn_id=turn_id,
        assistant_final_response=build_text_final_response(
            schema_version=schema_version,
            text=text,
        ),
        output_events=[],
        stage_summaries=[
            build_stage_summary(
                stage_name="input_normalization",
                status=StageStatus.COMPLETED,
            ),
            build_stage_summary(
                stage_name="final_response_assembly",
                status=StageStatus.COMPLETED,
            )
        ],
        provider_turn_refs=[],
        tool_result_refs=[],
        memory_result_refs=[],
        session_result_ref=None,
        error=None,
        metadata=dict(metadata or {}),
    )


def build_hard_failure_turn_result(
    *,
    schema_version: str,
    trace_id: str,
    turn_id: str,
    error_id: str,
    code: ErrorCode,
    message: str,
    source: str = "assistant_runtime",
    details: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> AssistantTurnResult:
    error = ErrorEnvelope(
        schema_version=schema_version,
        trace_id=trace_id,
        error_id=error_id,
        code=code,
        message=message,
        recoverable=False,
        source=source,
        details=dict(details or {}),
    )
    return AssistantTurnResult(
        schema_version=schema_version,
        trace_id=trace_id,
        turn_id=turn_id,
        assistant_final_response=None,
        output_events=[],
        stage_summaries=[
            build_stage_summary(
                stage_name="input_normalization",
                status=StageStatus.FAILED,
                error_ref=error_id,
            )
        ],
        provider_turn_refs=[],
        tool_result_refs=[],
        memory_result_refs=[],
        session_result_ref=None,
        error=error,
        metadata=dict(metadata or {}),
    )
