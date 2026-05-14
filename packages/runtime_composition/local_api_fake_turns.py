from __future__ import annotations

from typing import Callable, Protocol

from packages.contracts import AssistantTurnInput, AssistantTurnResult

from .assistant_provider_bridge import run_fake_provider_assistant_bridge


class LocalApiFakeTurnRequest(Protocol):
    assistant_turn_input: AssistantTurnInput
    model: str | None
    instructions: str | None
    previous_response_id: str | None
    provider_options: dict[str, object]


LocalApiFakeTurnHandler = Callable[[LocalApiFakeTurnRequest], AssistantTurnResult]


def create_local_api_fake_turn_handler() -> LocalApiFakeTurnHandler:
    def handle_fake_turn(request: LocalApiFakeTurnRequest) -> AssistantTurnResult:
        return run_fake_provider_assistant_bridge(
            request.assistant_turn_input,
            model=request.model,
            instructions=request.instructions,
            previous_response_id=request.previous_response_id,
            provider_options=request.provider_options,
        )

    return handle_fake_turn
