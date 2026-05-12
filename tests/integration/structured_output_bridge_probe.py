from __future__ import annotations

from typing import Any

from packages.assistant_runtime.structured_output_turn_result import (
    consume_structured_output_as_turn_result,
)
from packages.contracts import AssistantFinalResponse, AssistantTurnResult
from packages.provider_runtime.provider_runtime import (
    ProviderRuntimeConfig,
    map_provider_raw_output_to_structured_result,
)
from packages.provider_structured_output.fallback_result import (
    StructuredOutputFallbackResult,
)
from packages.provider_structured_output.handoff import (
    build_structured_output_handoff_draft,
)
from packages.telemetry import TelemetrySink


def bridge_provider_runtime_raw_output_to_assistant_turn(
    *,
    provider_name: str,
    raw_output_text: str,
    schema_version: str = "0.1.1-draft",
    trace_id: str | None = None,
    turn_id: str | None = None,
    telemetry_sink: TelemetrySink | None = None,
) -> AssistantTurnResult:
    effective_trace_id = trace_id or f"trace-{provider_name}-bridge-proof"
    effective_turn_id = turn_id or f"turn-{provider_name}-bridge-proof"
    provider_result = map_provider_raw_output_to_structured_result(
        config=ProviderRuntimeConfig(provider_name=provider_name),
        schema_version=schema_version,
        trace_id=effective_trace_id,
        turn_id=effective_turn_id,
        target_contract="AssistantFinalResponse",
        raw_output_text=raw_output_text,
        target_model=AssistantFinalResponse,
    )
    return bridge_structured_output_result_to_assistant_turn(
        provider_result,
        telemetry_sink=telemetry_sink,
    )


def bridge_structured_output_result_to_assistant_turn(
    provider_result: StructuredOutputFallbackResult,
    *,
    telemetry_sink: TelemetrySink | None = None,
) -> AssistantTurnResult:
    return consume_structured_output_as_turn_result(
        provider_result_to_handoff_dict(provider_result),
        telemetry_sink=telemetry_sink,
    )


def provider_result_to_handoff_dict(
    provider_result: StructuredOutputFallbackResult,
) -> dict[str, Any]:
    handoff = build_structured_output_handoff_draft(provider_result)
    return handoff.model_dump(exclude_none=True, exclude_defaults=True)


def bridge_handoff_dict_to_assistant_turn(
    handoff_data: dict[str, Any],
    *,
    telemetry_sink: TelemetrySink | None = None,
) -> AssistantTurnResult:
    return consume_structured_output_as_turn_result(
        dict(handoff_data),
        telemetry_sink=telemetry_sink,
    )
