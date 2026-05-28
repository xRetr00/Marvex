"""Tests for the agentic provider-loop helpers used by the default route."""

from packages.contracts import (
    AssistantFinalResponse,
    AssistantFinishReason,
    AssistantResponseType,
    AssistantTurnInput,
    AssistantTurnResult,
    ErrorCode,
    ErrorEnvelope,
    OutputChannelIntent,
    ProviderTurnRef,
    StageStatus,
)
from packages.core.orchestration.agentic_loop import (
    AGENTIC_LOOP_HARD_CEILING,
    AGENTIC_MAX_STEPS_ENV,
    continuation_turn_input,
    provider_response_id,
    provider_truncated,
    resolve_agentic_max_steps,
    should_continue_provider_loop,
)


def _stub_result(
    *,
    finish_reason: AssistantFinishReason = AssistantFinishReason.STOP,
    error: ErrorEnvelope | None = None,
    response_id: str | None = "resp-1",
) -> AssistantTurnResult:
    final = AssistantFinalResponse(
        schema_version="0.1.1-draft",
        response_type=AssistantResponseType.TEXT,
        text="reply",
        payload_ref=None,
        output_channel_intent=OutputChannelIntent.DISPLAY,
        safe_for_display=True,
        safe_for_speech=True,
        memory_write_candidate_hint=False,
        finish_reason=finish_reason,
        metadata={},
    )
    provider_refs = []
    if response_id:
        provider_refs.append(
            ProviderTurnRef(
                ref_type="provider_turn",
                ref_id=response_id,
                stage_name="provider_stage",
                provider_name="test",
                status=StageStatus.COMPLETED,
                trace_id="trace-1",
            )
        )
    return AssistantTurnResult(
        schema_version="0.1.1-draft",
        trace_id="trace-1",
        turn_id="turn-1",
        assistant_final_response=final,
        output_events=[],
        stage_summaries=[],
        provider_turn_refs=provider_refs,
        tool_result_refs=[],
        memory_result_refs=[],
        session_result_ref=None,
        error=error,
        metadata={},
    )


def test_resolve_agentic_max_steps_uses_planner_default(monkeypatch):
    monkeypatch.delenv(AGENTIC_MAX_STEPS_ENV, raising=False)
    assert resolve_agentic_max_steps(3) == 3
    assert resolve_agentic_max_steps(0) == 1
    assert resolve_agentic_max_steps(99) == AGENTIC_LOOP_HARD_CEILING


def test_resolve_agentic_max_steps_env_override(monkeypatch):
    monkeypatch.setenv(AGENTIC_MAX_STEPS_ENV, "4")
    assert resolve_agentic_max_steps(2) == 4
    monkeypatch.setenv(AGENTIC_MAX_STEPS_ENV, "99")
    assert resolve_agentic_max_steps(2) == AGENTIC_LOOP_HARD_CEILING
    monkeypatch.setenv(AGENTIC_MAX_STEPS_ENV, "garbage")
    assert resolve_agentic_max_steps(2) == 2


def test_provider_response_id_reads_refs():
    result = _stub_result(response_id="resp-xyz")
    assert provider_response_id(result) == "resp-xyz"


def test_provider_response_id_empty_when_none():
    result = _stub_result(response_id=None)
    assert provider_response_id(result) is None


def test_provider_truncated_on_length_finish():
    assert provider_truncated(_stub_result(finish_reason=AssistantFinishReason.LENGTH))
    assert not provider_truncated(_stub_result(finish_reason=AssistantFinishReason.STOP))


def test_provider_truncated_false_on_error():
    err = ErrorEnvelope(
        schema_version="0.1.1-draft",
        trace_id="trace-1",
        error_id="e-1",
        code=ErrorCode.PROVIDER_ERROR,
        message="boom",
        recoverable=True,
        source="test",
        details={},
    )
    assert not provider_truncated(
        _stub_result(finish_reason=AssistantFinishReason.LENGTH, error=err)
    )


def test_should_continue_provider_loop_only_when_truncated_and_room():
    trunc = _stub_result(finish_reason=AssistantFinishReason.LENGTH)
    stop = _stub_result(finish_reason=AssistantFinishReason.STOP)

    assert should_continue_provider_loop(trunc, step_index=0, max_steps=3)
    assert not should_continue_provider_loop(trunc, step_index=2, max_steps=3)
    assert not should_continue_provider_loop(stop, step_index=0, max_steps=3)
    assert not should_continue_provider_loop(None, step_index=0, max_steps=3)


def test_continuation_turn_input_swaps_user_input():
    turn = AssistantTurnInput(
        schema_version="0.1.1-draft",
        trace_id="trace-1",
        turn_id="turn-1",
        input_event_id="event-1",
        session_ref=None,
        identity_ref=None,
        user_visible_input="Original question",
        assistant_mode="default",
        policy_context={"requested_capabilities": [], "sensitivity": "normal"},
        metadata={},
    )
    follow = continuation_turn_input(turn, step_index=0)
    assert follow.user_visible_input != "Original question"
    assert "continuation step 2" in follow.user_visible_input.lower()
