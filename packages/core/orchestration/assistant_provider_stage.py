from __future__ import annotations

from typing import Any

from packages.assistant_runtime.provider_stage import (
    AssistantRuntimeProvider,
    run_provider_stage_turn,
)
from packages.contracts import AssistantTurnInput, AssistantTurnResult
from packages.telemetry import TelemetrySink


def run_assistant_provider_stage_turn(
    turn_input: AssistantTurnInput,
    *,
    provider: AssistantRuntimeProvider,
    model: str,
    instructions: str | None = None,
    previous_response_id: str | None = None,
    provider_options: dict[str, Any] | None = None,
    telemetry_sink: TelemetrySink | None = None,
) -> AssistantTurnResult:
    return run_provider_stage_turn(
        turn_input,
        provider=provider,
        model=model,
        instructions=instructions,
        previous_response_id=previous_response_id,
        provider_options=provider_options,
        telemetry_sink=telemetry_sink,
    )
