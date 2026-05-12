from __future__ import annotations

from typing import Any

from packages.contracts import AssistantTurnInput, AssistantTurnResult
from packages.core.orchestration.assistant_provider_stage import (
    run_assistant_provider_stage_turn,
)
from packages.provider_runtime import ProviderRuntimeConfig, create_provider
from packages.telemetry import TelemetrySink


FAKE_PROVIDER_NAME = "fake"


def run_fake_provider_assistant_bridge(
    turn_input: AssistantTurnInput,
    *,
    model: str,
    instructions: str | None = None,
    previous_response_id: str | None = None,
    provider_options: dict[str, Any] | None = None,
    telemetry_sink: TelemetrySink | None = None,
) -> AssistantTurnResult:
    provider = create_provider(ProviderRuntimeConfig(provider_name=FAKE_PROVIDER_NAME))
    return run_assistant_provider_stage_turn(
        turn_input,
        provider=provider,
        model=model,
        instructions=instructions,
        previous_response_id=previous_response_id,
        provider_options=provider_options,
        telemetry_sink=telemetry_sink,
    )
