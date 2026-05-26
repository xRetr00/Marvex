from __future__ import annotations

from typing import Protocol, runtime_checkable

from packages.contracts import AssistantTurnInput, AssistantTurnResult


@runtime_checkable
class CoreTurnExecutorPort(Protocol):
    def submit_turn(
        self,
        turn_input: AssistantTurnInput,
        previous_response_id: str | None = None,
    ) -> AssistantTurnResult:
        ...
