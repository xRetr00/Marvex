from __future__ import annotations

from packages.contracts import TurnInput, TurnOutput
from packages.core.orchestration import TurnOrchestrator
from packages.provider_runtime import ProviderRuntimeConfig, create_provider


def run_provider_foundation_turn(
    turn_input: TurnInput,
    *,
    provider_name: str,
    model: str,
    instructions: str | None = None,
) -> TurnOutput:
    provider = create_provider(ProviderRuntimeConfig(provider_name=provider_name))
    return TurnOrchestrator(
        provider,
        model=model,
        instructions=instructions,
    ).run_turn(turn_input)
