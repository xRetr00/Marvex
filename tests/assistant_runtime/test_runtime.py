from datetime import UTC, datetime

import pytest

from packages.assistant_runtime import build_text_input_event, build_turn_input_from_event
from packages.assistant_runtime.runtime import AssistantTurnRuntime
from packages.contracts import AssistantTurnResult, ErrorCode, StageStatus


def _turn_input(user_visible_input: str | None = "Hello"):
    event = build_text_input_event(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        event_id="event-001",
        text=user_visible_input or "",
        timestamp=datetime(2026, 5, 4, 12, 0, tzinfo=UTC),
    )
    turn_input = build_turn_input_from_event(
        schema_version="0.1.1-draft",
        trace_id="trace-001",
        turn_id="turn-001",
        input_event=event,
    )
    if user_visible_input is None:
        return turn_input.model_copy(update={"user_visible_input": None})
    return turn_input


def test_runtime_accepts_valid_assistant_turn_input():
    runtime = AssistantTurnRuntime()

    result = runtime.run(_turn_input("Hello"))

    assert isinstance(result, AssistantTurnResult)


def test_runtime_returns_valid_result_and_preserves_trace_and_turn_ids():
    runtime = AssistantTurnRuntime()
    turn_input = _turn_input("Hello")

    result = runtime.run(turn_input)

    assert result.trace_id == turn_input.trace_id
    assert result.turn_id == turn_input.turn_id
    assert result.assistant_final_response is not None
    assert result.assistant_final_response.text == "Assistant runtime received input."


def test_runtime_creates_no_provider_refs_or_provider_response_id():
    result = AssistantTurnRuntime().run(_turn_input("Hello"))
    dumped = result.model_dump()

    assert result.provider_turn_refs == []
    assert "provider_response_id" not in dumped


@pytest.mark.parametrize("user_visible_input", [None, "", "   "])
def test_runtime_hard_failure_behavior_is_contract_valid(user_visible_input):
    result = AssistantTurnRuntime().run(_turn_input(user_visible_input))

    assert isinstance(result, AssistantTurnResult)
    assert result.trace_id == "trace-001"
    assert result.turn_id == "turn-001"
    assert result.assistant_final_response is None
    assert result.error is not None
    assert result.error.code == ErrorCode.VALIDATION_ERROR
    assert result.stage_summaries[0].status == StageStatus.FAILED
