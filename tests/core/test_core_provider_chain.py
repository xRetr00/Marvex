"""Provider response-id chaining (services.core.main + agentic loop).

Regression for the context-continuity bug: the core built agentic/clarification
results with an empty ``provider_turn_refs``, so the shell could never echo a
``previous_response_id`` and every follow-up turn was sent to the model with no
conversation history. These tests lock in that a turn carries the provider's
response id forward.
"""

from __future__ import annotations

from packages.contracts import (
    AssistantMode,
    AssistantTurnInput,
    PolicyContext,
    Sensitivity,
)
from packages.core.orchestration.agentic_loop import provider_response_id
from packages.core.orchestration.agentic_tools import (
    LoopResult,
    ProviderStep,
    run_tool_loop,
)
from services.core.main import _entrypoint_text_result


def _turn_input() -> AssistantTurnInput:
    return AssistantTurnInput(
        schema_version="0.1.1-draft",
        trace_id="trace-chain",
        turn_id="turn-chain",
        input_event_id="event-chain",
        session_ref=None,
        identity_ref=None,
        user_visible_input="read the file",
        assistant_mode=AssistantMode.DEFAULT,
        policy_context=PolicyContext(requested_capabilities=[], sensitivity=Sensitivity.NORMAL),
        metadata={},
    )


def test_run_tool_loop_final_carries_response_id():
    # A plain answer (no tool calls) must still surface the provider response id
    # so the turn can be chained.
    step = ProviderStep(output_text="hi", tool_calls=[], response_id="resp-final", error=False)
    result: LoopResult = run_tool_loop(
        send=lambda _input, _msgs, _prev: step,
        registry=object(),
        request_builder=lambda *_a, **_k: None,
        max_steps=3,
        initial_input="hello",
    )
    assert result.status == "final"
    assert result.response_id == "resp-final"


def test_entrypoint_text_result_emits_chainable_provider_ref():
    result = _entrypoint_text_result(
        _turn_input(),
        text="done",
        metadata={},
        stage_name="agentic_tool_loop",
        provider_response_id="resp-9",
        provider_name="lmstudio_responses",
    )
    # Round-trips through the same helper the shell uses to read the next
    # previous_response_id.
    assert provider_response_id(result) == "resp-9"
    assert result.provider_turn_refs[0].ref_id == "resp-9"


def test_entrypoint_text_result_without_response_id_has_no_refs():
    result = _entrypoint_text_result(
        _turn_input(),
        text="done",
        metadata={},
        stage_name="agentic_tool_loop",
    )
    assert result.provider_turn_refs == []
