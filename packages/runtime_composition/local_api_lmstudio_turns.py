from __future__ import annotations

from typing import Callable, Protocol

from packages.contracts import (
    AssistantTurnInput,
    AssistantTurnResult,
    ErrorCode,
    ErrorEnvelope,
)
from packages.telemetry import TelemetrySink

from .assistant_provider_bridge import run_lmstudio_responses_assistant_bridge


LOCAL_API_LMSTUDIO_RESPONSES_EXECUTION_MODE = "assistant_runtime_lmstudio_responses"
ALLOWED_LMSTUDIO_PROVIDER_OPTIONS = frozenset(
    {"temperature", "max_output_tokens", "top_p", "timeout"}
)


class LocalApiLmstudioTurnRequest(Protocol):
    schema_version: str
    execution_mode: str
    assistant_turn_input: AssistantTurnInput
    model: str | None
    instructions: str | None
    previous_response_id: str | None
    provider_options: dict[str, object]


LocalApiLmstudioTurnHandler = Callable[
    [LocalApiLmstudioTurnRequest], AssistantTurnResult
]


def create_local_api_lmstudio_turn_handler(
    *,
    telemetry_sink: TelemetrySink | None = None,
    lmstudio_responses_api_key: str | None = None,
) -> LocalApiLmstudioTurnHandler:
    def handle_lmstudio_turn(
        request: LocalApiLmstudioTurnRequest,
    ) -> AssistantTurnResult:
        if request.execution_mode != LOCAL_API_LMSTUDIO_RESPONSES_EXECUTION_MODE:
            return _validation_result(request, "unsupported_execution_mode")
        if not isinstance(request.model, str) or not request.model.strip():
            return _validation_result(request, "invalid_model")
        rejected_options = _rejected_provider_options(request.provider_options)
        if rejected_options:
            return _validation_result(
                request,
                "invalid_provider_options",
                details={"rejected_provider_options": rejected_options},
            )

        kwargs = {
            "model": request.model,
            "instructions": request.instructions,
            "previous_response_id": request.previous_response_id,
            "provider_options": request.provider_options,
        }
        if telemetry_sink is not None:
            kwargs["telemetry_sink"] = telemetry_sink
        if lmstudio_responses_api_key is not None:
            kwargs["lmstudio_responses_api_key"] = lmstudio_responses_api_key
        return run_lmstudio_responses_assistant_bridge(
            request.assistant_turn_input,
            **kwargs,
        )

    return handle_lmstudio_turn


def _validation_result(
    request: LocalApiLmstudioTurnRequest,
    reason: str,
    *,
    details: dict[str, object] | None = None,
) -> AssistantTurnResult:
    turn_input = request.assistant_turn_input
    return AssistantTurnResult(
        schema_version=request.schema_version,
        trace_id=turn_input.trace_id,
        turn_id=turn_input.turn_id,
        assistant_final_response=None,
        output_events=[],
        stage_summaries=[],
        provider_turn_refs=[],
        tool_result_refs=[],
        memory_result_refs=[],
        session_result_ref=None,
        error=ErrorEnvelope(
            schema_version=request.schema_version,
            trace_id=turn_input.trace_id,
            error_id=f"{turn_input.turn_id}:local-api-lmstudio-validation",
            code=ErrorCode.VALIDATION_ERROR,
            message="Local API LM Studio turn request validation failed.",
            recoverable=False,
            source="runtime_composition",
            details={"reason": reason, **dict(details or {})},
        ),
        metadata={},
    )


def _rejected_provider_options(provider_options: dict[str, object]) -> list[str]:
    return sorted(
        name for name in provider_options if name not in ALLOWED_LMSTUDIO_PROVIDER_OPTIONS
    )
