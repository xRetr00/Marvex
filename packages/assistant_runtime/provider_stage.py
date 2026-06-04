from __future__ import annotations

from typing import Any, Protocol

from packages.contracts import (
    AssistantFinishReason,
    AssistantTurnInput,
    AssistantTurnResult,
    ErrorCode,
    ErrorEnvelope,
    FinishReason,
    ProviderRequest,
    ProviderResponse,
    ProviderTurnRef,
    StageStatus,
    TraceLevel,
    TraceStage,
)
from packages.prompt_harness_runtime.provider_compiler import ProviderPromptPayload
from packages.telemetry import TelemetrySink, make_trace_event

from .result_assembly import build_stage_summary, build_text_final_response


PROVIDER_STAGE_NAME = "provider_stage"
ERROR_ID_SUFFIX = "provider-stage"


class AssistantRuntimeProvider(Protocol):
    def send(self, request: ProviderRequest) -> ProviderResponse:
        ...


def run_provider_stage_turn(
    turn_input: AssistantTurnInput,
    *,
    provider: AssistantRuntimeProvider,
    model: str,
    instructions: str | None = None,
    provider_prompt: ProviderPromptPayload | None = None,
    previous_response_id: str | None = None,
    provider_options: dict[str, Any] | None = None,
    telemetry_sink: TelemetrySink | None = None,
) -> AssistantTurnResult:
    if provider_prompt is None and _blank(turn_input.user_visible_input):
        return _error_result(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            code=ErrorCode.VALIDATION_ERROR,
            message="AssistantTurnInput requires user_visible_input for provider stage.",
            stage_name="input_normalization",
        )

    request = ProviderRequest(
        schema_version=turn_input.schema_version,
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        model=model,
        input_text=provider_prompt.input_text if provider_prompt is not None else turn_input.user_visible_input or "",
        instructions=provider_prompt.instructions if provider_prompt is not None else instructions,
        previous_response_id=previous_response_id,
        provider_options=dict(provider_options or {}),
    )
    _emit(
        telemetry_sink=telemetry_sink,
        schema_version=turn_input.schema_version,
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        stage=TraceStage.PROVIDER_REQUEST_CREATED,
        message="Provider request created.",
        data={
            "stage": PROVIDER_STAGE_NAME,
            "model": model,
            "previous_response_id_present": bool(previous_response_id),
        },
    )
    _emit(
        telemetry_sink=telemetry_sink,
        schema_version=turn_input.schema_version,
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        stage=TraceStage.PROVIDER_REQUEST_SENT,
        message="Provider request sent.",
        data={
            "stage": PROVIDER_STAGE_NAME,
            "model": model,
            "previous_response_id_present": bool(previous_response_id),
        },
    )

    try:
        response = provider.send(request)
    except Exception as exc:
        code, message = _provider_exception_error(exc)
        _emit(
            telemetry_sink=telemetry_sink,
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            stage=TraceStage.PROVIDER_RESPONSE_RECEIVED,
            message="Provider response failed.",
            data={
                "stage": PROVIDER_STAGE_NAME,
                "status": "provider_error",
                "error_code": code.value,
                "provider_response_id_present": False,
            },
            level=TraceLevel.ERROR,
        )
        return _error_result(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            code=code,
            message=message,
        )

    provider_ref = _provider_ref(response)
    if response.error is not None:
        _emit_provider_response(
            telemetry_sink=telemetry_sink,
            response=response,
            status="provider_error",
            level=TraceLevel.ERROR,
        )
        return _error_result(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            code=response.error.code,
            message=response.error.message,
            error_id=response.error.error_id,
            provider_refs=[provider_ref],
        )

    if _blank(response.output_text):
        _emit_provider_response(
            telemetry_sink=telemetry_sink,
            response=response,
            status="invalid_provider_output",
            level=TraceLevel.ERROR,
        )
        return _error_result(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            code=ErrorCode.VALIDATION_ERROR,
            message="Provider output was empty.",
            provider_refs=[provider_ref],
        )

    final_response = build_text_final_response(
        schema_version=turn_input.schema_version,
        text=response.output_text,
        finish_reason=_assistant_finish_reason(response.finish_reason),
    )
    _emit_provider_response(
        telemetry_sink=telemetry_sink,
        response=response,
        status="success",
    )
    _emit(
        telemetry_sink=telemetry_sink,
        schema_version=turn_input.schema_version,
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        stage=TraceStage.FINAL_RESPONSE_CREATED,
        message="Final response created.",
        data={"response_type": final_response.response_type.value},
    )
    _emit(
        telemetry_sink=telemetry_sink,
        schema_version=turn_input.schema_version,
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        stage=TraceStage.TURN_COMPLETED,
        message="Turn completed.",
        data={"status": "success"},
    )
    return AssistantTurnResult(
        schema_version=turn_input.schema_version,
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        assistant_final_response=final_response,
        output_events=[],
        stage_summaries=[
            build_stage_summary(
                stage_name="input_normalization",
                status=StageStatus.COMPLETED,
            ),
            build_stage_summary(
                stage_name=PROVIDER_STAGE_NAME,
                status=StageStatus.COMPLETED,
                error_ref=None,
            ),
            build_stage_summary(
                stage_name="final_response_assembly",
                status=StageStatus.COMPLETED,
            ),
        ],
        provider_turn_refs=[provider_ref],
        tool_result_refs=[],
        memory_result_refs=[],
        session_result_ref=None,
        error=None,
        metadata={
            "provider_model": model,
            "provider_usage": dict(response.usage),
        },
    )


def _error_result(
    *,
    schema_version: str,
    trace_id: str,
    turn_id: str,
    code: ErrorCode,
    message: str,
    stage_name: str = PROVIDER_STAGE_NAME,
    error_id: str | None = None,
    provider_refs: list[ProviderTurnRef] | None = None,
) -> AssistantTurnResult:
    resolved_error_id = error_id or f"{turn_id}:{ERROR_ID_SUFFIX}"
    error = ErrorEnvelope(
        schema_version=schema_version,
        trace_id=trace_id,
        error_id=resolved_error_id,
        code=code,
        message=message,
        recoverable=False,
        source="assistant_runtime",
        details={},
    )
    stage_summaries = []
    if stage_name == PROVIDER_STAGE_NAME:
        stage_summaries.append(
            build_stage_summary(
                stage_name="input_normalization",
                status=StageStatus.COMPLETED,
            )
        )
    stage_summaries.append(
        build_stage_summary(
            stage_name=stage_name,
            status=StageStatus.FAILED,
            error_ref=resolved_error_id,
        )
    )
    return AssistantTurnResult(
        schema_version=schema_version,
        trace_id=trace_id,
        turn_id=turn_id,
        assistant_final_response=None,
        output_events=[],
        stage_summaries=stage_summaries,
        provider_turn_refs=list(provider_refs or []),
        tool_result_refs=[],
        memory_result_refs=[],
        session_result_ref=None,
        error=error,
        metadata={},
    )


def _provider_ref(response: ProviderResponse) -> ProviderTurnRef:
    return ProviderTurnRef(
        ref_type="provider_turn",
        ref_id=response.response_id or f"{response.turn_id}:provider-turn",
        stage_name=PROVIDER_STAGE_NAME,
        provider_name=response.provider_name,
        status=StageStatus.FAILED if response.error is not None else StageStatus.COMPLETED,
        trace_id=response.trace_id,
    )


def _provider_exception_error(exc: Exception) -> tuple[ErrorCode, str]:
    if isinstance(exc, TimeoutError):
        return ErrorCode.PROVIDER_TIMEOUT, "Provider request timed out."
    if isinstance(exc, ConnectionError):
        return ErrorCode.PROVIDER_UNAVAILABLE, "Provider unavailable."
    return ErrorCode.PROVIDER_ERROR, "Provider stage failed."


def _emit_provider_response(
    *,
    telemetry_sink: TelemetrySink | None,
    response: ProviderResponse,
    status: str,
    level: TraceLevel = TraceLevel.INFO,
) -> None:
    data: dict[str, object] = {
        "stage": PROVIDER_STAGE_NAME,
        "status": status,
        "provider_name": response.provider_name,
        "finish_reason": response.finish_reason.value,
        "provider_response_id_present": bool(response.response_id),
    }
    if response.error is not None:
        data["error_code"] = response.error.code.value
    _emit(
        telemetry_sink=telemetry_sink,
        schema_version=response.schema_version,
        trace_id=response.trace_id,
        turn_id=response.turn_id,
        stage=TraceStage.PROVIDER_RESPONSE_RECEIVED,
        message="Provider response received.",
        data=data,
        level=level,
    )


def _emit(
    *,
    telemetry_sink: TelemetrySink | None,
    schema_version: str,
    trace_id: str,
    turn_id: str,
    stage: TraceStage,
    message: str,
    data: dict[str, object],
    level: TraceLevel = TraceLevel.INFO,
) -> None:
    if telemetry_sink is None:
        return
    telemetry_sink.emit(
        make_trace_event(
            schema_version=schema_version,
            trace_id=trace_id,
            turn_id=turn_id,
            stage=stage,
            level=level,
            message=message,
            data=data,
        )
    )


def _assistant_finish_reason(value: FinishReason) -> AssistantFinishReason:
    return AssistantFinishReason(value.value)


def _blank(value: str | None) -> bool:
    return value is None or not value.strip()
