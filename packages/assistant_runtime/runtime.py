from __future__ import annotations

from packages.contracts import AssistantTurnInput, AssistantTurnResult, ErrorCode

from .result_assembly import (
    build_hard_failure_turn_result,
    build_text_success_turn_result,
)


def _blank(value: str | None) -> bool:
    return value is None or not value.strip()


class AssistantTurnRuntime:
    def run(self, turn_input: AssistantTurnInput) -> AssistantTurnResult:
        if _blank(turn_input.user_visible_input) or _blank(turn_input.input_event_id):
            return build_hard_failure_turn_result(
                schema_version=turn_input.schema_version,
                trace_id=turn_input.trace_id,
                turn_id=turn_input.turn_id,
                error_id=f"{turn_input.turn_id}:input-validation",
                code=ErrorCode.VALIDATION_ERROR,
                message="AssistantTurnInput requires user_visible_input for this skeleton.",
            )

        return build_text_success_turn_result(
            schema_version=turn_input.schema_version,
            trace_id=turn_input.trace_id,
            turn_id=turn_input.turn_id,
            text="Assistant runtime received input.",
        )
