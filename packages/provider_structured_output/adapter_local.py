from __future__ import annotations

from .fallback_result import (
    StructuredOutputFallbackResult,
    TargetModel,
    validate_raw_structured_output,
)


def map_adapter_raw_output_to_structured_result(
    *,
    schema_version: str,
    trace_id: str,
    turn_id: str,
    target_contract: str,
    raw_output_text: str,
    target_model: type[TargetModel],
    include_raw_preview: bool = False,
) -> StructuredOutputFallbackResult:
    return validate_raw_structured_output(
        schema_version=schema_version,
        trace_id=trace_id,
        turn_id=turn_id,
        target_contract=target_contract,
        raw_output_text=raw_output_text,
        target_model=target_model,
        include_raw_preview=include_raw_preview,
    )
